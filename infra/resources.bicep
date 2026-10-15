// Lasso: all Azure resources. Keyless everywhere: one user-assigned managed identity, RBAC data-plane roles.
param location string
param environmentName string
param tags object
param fastModelName string
param fastModelVersion string
param writerModelName string
param writerModelVersion string
param modelCapacity int
@secure()
param adminKey string
param apiImage string
param agentsImage string
param feedImage string

var token = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))
var placeholderImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// ----------------------------------------------------------------- identity + monitoring
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-lasso-${token}'
  location: location
  tags: tags
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-lasso-${token}'
  location: location
  tags: tags
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-lasso-${token}'
  location: location
  tags: tags
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: logs.id }
}

// ----------------------------------------------------------------- container registry
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'crlasso${token}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'acrpull')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ----------------------------------------------------------------- Microsoft Foundry
resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: 'aif-lasso-${token}'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: 'aif-lasso-${token}'
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: 'lasso'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: { displayName: 'Lasso', description: 'Lasso multi-agent match companion' }
  dependsOn: [fastDeployment, writerDeployment]
}

resource fastDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: fastModelName
  sku: { name: 'GlobalStandard', capacity: modelCapacity }
  properties: { model: { format: 'OpenAI', name: fastModelName, version: fastModelVersion } }
}

resource writerDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (writerModelName != fastModelName) {
  parent: foundry
  name: writerModelName
  sku: { name: 'GlobalStandard', capacity: modelCapacity }
  properties: { model: { format: 'OpenAI', name: writerModelName, version: writerModelVersion } }
}

resource foundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, identity.id, 'azure-ai-user')
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, identity.id, 'openai-user')
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Listen: the API reads stories aloud with Azure AI Speech on this same account (keyless). Cognitive Services
// User covers speech synthesis.
resource foundrySpeechUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, identity.id, 'cognitive-services-user')
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ----------------------------------------------------------------- Event Hubs (live match events)
resource eventHubs 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: 'evhns-lasso-${token}'
  location: location
  tags: tags
  sku: { name: 'Basic', tier: 'Basic', capacity: 1 }
  properties: { disableLocalAuth: true, minimumTlsVersion: '1.2' }
}

resource matchEvents 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubs
  name: 'match-events'
  properties: { partitionCount: 2, messageRetentionInDays: 1 }
}

resource ehSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHubs.id, identity.id, 'sender')
  scope: eventHubs
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2b629674-e913-4c01-ae53-ef4638d8f975')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource ehReceiver 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHubs.id, identity.id, 'receiver')
  scope: eventHubs
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a638d3c7-ab3a-418d-83e6-5f17a39d4fde')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ----------------------------------------------------------------- Cosmos DB (serverless)
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'cosmos-lasso-${token}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [{ locationName: location, failoverPriority: 0 }]
    capabilities: [{ name: 'EnableServerless' }]
    disableLocalAuth: true
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: 'lasso'
  properties: { resource: { id: 'lasso' } }
}

var containers = [
  { name: 'users', pk: '/id' }
  { name: 'calls', pk: '/user_id' }
  { name: 'leagues', pk: '/id' }
]

resource cosmosContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for c in containers: {
  parent: cosmosDb
  name: c.name
  properties: { resource: { id: c.name, partitionKey: { paths: [c.pk], kind: 'Hash' } } }
}]

resource cosmosData 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmos
  name: guid(cosmos.id, identity.id, 'data-contributor')
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: identity.properties.principalId
    scope: cosmos.id
  }
}

// ----------------------------------------------------------------- Web PubSub (realtime fan-out)
resource webPubSub 'Microsoft.SignalRService/webPubSub@2024-03-01' = {
  name: 'wps-lasso-${token}'
  location: location
  tags: tags
  sku: { name: 'Standard_S1', tier: 'Standard', capacity: 1 }
  properties: { disableLocalAuth: true, publicNetworkAccess: 'Enabled' }
}

resource wpsOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(webPubSub.id, identity.id, 'owner')
  scope: webPubSub
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '12cf5a90-567b-43ae-8102-96cf46c7d9b4')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ----------------------------------------------------------------- Container Apps
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-lasso-${token}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: { customerId: logs.properties.customerId, sharedKey: logs.listKeys().primarySharedKey }
    }
  }
}

var apiName = 'ca-api-${token}'
var agentsName = 'ca-agents-${token}'
var apiUrl = 'https://${apiName}.${env.properties.defaultDomain}'
var agentsUrl = 'https://${agentsName}.${env.properties.defaultDomain}'
var ehNamespace = '${eventHubs.name}.servicebus.windows.net'

var common = [
  { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
  { name: 'OTEL_SERVICE_NAME', value: 'lasso' }
]

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiName
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8000, transport: 'auto', allowInsecure: false }
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
      secrets: [{ name: 'admin-key', value: adminKey }]
    }
    template: {
      // Match rooms live in memory, so the API runs as a single, always-on replica.
      scale: { minReplicas: 1, maxReplicas: 1 }
      containers: [{
        name: 'api'
        image: empty(apiImage) ? placeholderImage : apiImage
        resources: { cpu: json('1.0'), memory: '2Gi' }
        env: concat(common, [
          { name: 'LASSO_EVENT_SOURCE', value: 'eventhubs' }
          { name: 'EVENTHUB_FULLY_QUALIFIED_NAMESPACE', value: ehNamespace }
          { name: 'EVENTHUB_NAME', value: matchEvents.name }
          { name: 'WEBPUBSUB_ENDPOINT', value: 'https://${webPubSub.properties.hostName}' }
          { name: 'WEBPUBSUB_HUB', value: 'lasso' }
          { name: 'COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
          { name: 'LASSO_AGENTS_URL', value: '${agentsUrl}/' }
          { name: 'LASSO_ADMIN_KEY', secretRef: 'admin-key' }
          { name: 'LASSO_SPEECH_REGION', value: foundry.location }
          { name: 'LASSO_SPEECH_RESOURCE_ID', value: foundry.id }
          { name: 'OTEL_SERVICE_NAME', value: 'lasso-api' }
        ])
      }]
    }
  }
  dependsOn: [acrPull, cosmosData, wpsOwner, ehReceiver]
}

resource agents 'Microsoft.App/containerApps@2024-03-01' = {
  name: agentsName
  location: location
  tags: union(tags, { 'azd-service-name': 'agents' })
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8100, transport: 'auto', allowInsecure: false }
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
    }
    template: {
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '10' } } }]
      }
      containers: [{
        name: 'agents'
        image: empty(agentsImage) ? placeholderImage : agentsImage
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: concat(common, [
          { name: 'FOUNDRY_PROJECT_ENDPOINT', value: 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${project.name}' }
          { name: 'FOUNDRY_MODEL', value: fastDeployment.name }
          { name: 'FOUNDRY_WRITER_MODEL', value: writerModelName }
          { name: 'LASSO_MCP_URL', value: '${apiUrl}/mcp/' }
          { name: 'LASSO_AGENTS_PUBLIC_URL', value: '${agentsUrl}/' }
          { name: 'OTEL_SERVICE_NAME', value: 'lasso-agents' }
        ])
      }]
    }
  }
  dependsOn: [acrPull, foundryUser, foundryOpenAIUser, writerDeployment]
}

resource feed 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-feed-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'feed' })
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
    }
    template: {
      scale: { minReplicas: 1, maxReplicas: 1 }
      containers: [{
        name: 'feed'
        image: empty(feedImage) ? placeholderImage : feedImage
        resources: { cpu: json('0.25'), memory: '0.5Gi' }
        env: concat(common, [
          { name: 'EVENTHUB_FULLY_QUALIFIED_NAMESPACE', value: ehNamespace }
          { name: 'EVENTHUB_NAME', value: matchEvents.name }
          { name: 'OTEL_SERVICE_NAME', value: 'lasso-feed' }
        ])
      }]
    }
  }
  dependsOn: [acrPull, ehSender]
}

output registryLoginServer string = registry.properties.loginServer
output apiUrl string = apiUrl
output agentsUrl string = agentsUrl
output foundryProjectEndpoint string = 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${project.name}'
