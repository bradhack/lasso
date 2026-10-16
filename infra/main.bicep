targetScope = 'subscription'

@minLength(1)
@maxLength(40)
@description('azd environment name, used to name the resource group and resources')
param environmentName string

@description('Primary region (East US 2 has broad Foundry model availability)')
param location string = 'eastus2'

@description('Fast model for the Stats, Gaffer and Game Master agents')
param fastModelName string = 'gpt-5-mini'
param fastModelVersion string = '2025-08-07'

@description('Writer model for the Narrator and Persona agents')
param writerModelName string = 'gpt-5-mini'
param writerModelVersion string = '2025-08-07'

@description('Tokens-per-minute capacity (thousands) for each model deployment')
param modelCapacity int = 50

@secure()
@description('Key for the demo admin endpoint (restart a match from a given minute). Set it once with `azd env set LASSO_ADMIN_KEY <value>` so it survives every provision; left empty, a stable key is derived for this environment.')
param adminKey string = ''

// Stable across provisions (newGuid() here used to rotate the key on every `azd provision`).
var effectiveAdminKey = empty(adminKey) ? '${uniqueString(subscription().id, environmentName, 'lasso-admin')}${uniqueString(environmentName, subscription().subscriptionId, 'key')}' : adminKey

@secure()
@description('Shared key the API sends with every request to the agents service, so only the API can run the agents. Left empty, a stable key is derived for this environment; override with `azd env set LASSO_AGENTS_KEY <value>`.')
param agentsKey string = ''
// Stable across provisions: both apps must always hold the same value.
var effectiveAgentsKey = empty(agentsKey) ? '${uniqueString(subscription().id, environmentName, 'lasso-agents')}${uniqueString(environmentName, subscription().subscriptionId, 'a2a')}' : agentsKey

param apiImage string = ''
param agentsImage string = ''
param feedImage string = ''

var tags = { 'azd-env-name': environmentName, app: 'lasso' }

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'lasso-resources'
  scope: rg
  params: {
    location: location
    environmentName: environmentName
    tags: tags
    fastModelName: fastModelName
    fastModelVersion: fastModelVersion
    writerModelName: writerModelName
    writerModelVersion: writerModelVersion
    modelCapacity: modelCapacity
    adminKey: effectiveAdminKey
    agentsKey: effectiveAgentsKey
    apiImage: apiImage
    agentsImage: agentsImage
    feedImage: feedImage
  }
}

output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryLoginServer
output LASSO_APP_URL string = resources.outputs.apiUrl
output LASSO_AGENTS_URL string = resources.outputs.agentsUrl
output LASSO_MCP_URL string = '${resources.outputs.apiUrl}/mcp/'
output FOUNDRY_PROJECT_ENDPOINT string = resources.outputs.foundryProjectEndpoint
