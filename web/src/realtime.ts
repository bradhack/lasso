/**
 * Realtime client for the json.webpubsub.azure.v1 subprotocol.
 * Works against Azure Web PubSub in the cloud and the API's compatible local hub.
 */
import { api } from "./api";

type Handler = (data: any, group: string | null) => void;

export class Realtime {
  private ws: WebSocket | null = null;
  private groups = new Set<string>();
  private handlers = new Set<Handler>();
  private ackId = 1;
  private retry = 0;
  private stopped = false;
  public connected = false;
  private statusListeners = new Set<(c: boolean) => void>();

  constructor(private userId: string) {}

  async start(): Promise<void> {
    this.stopped = false;
    try {
      const { url } = await api.negotiate(this.userId);
      const full = url.startsWith("ws") ? url : `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${url}`;
      const ws = new WebSocket(full, "json.webpubsub.azure.v1");
      this.ws = ws;
      ws.onopen = () => {
        this.retry = 0;
        this.setConnected(true);
        for (const g of this.groups) this.sendJoin(g);
      };
      ws.onmessage = (ev) => {
        let msg: any;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (msg.type !== "message") return;
        const data = typeof msg.data === "string" ? safeParse(msg.data) : msg.data;
        for (const h of this.handlers) h(data, msg.group ?? null);
      };
      ws.onclose = () => {
        this.setConnected(false);
        if (!this.stopped) this.reconnect();
      };
      ws.onerror = () => ws.close();
    } catch {
      this.reconnect();
    }
  }

  private reconnect() {
    const delay = Math.min(15000, 500 * 2 ** this.retry++);
    setTimeout(() => !this.stopped && this.start(), delay);
  }

  private setConnected(c: boolean) {
    this.connected = c;
    for (const l of this.statusListeners) l(c);
  }

  onStatus(l: (c: boolean) => void) {
    this.statusListeners.add(l);
    return () => this.statusListeners.delete(l);
  }

  private sendJoin(group: string) {
    if (this.ws?.readyState === WebSocket.OPEN)
      this.ws.send(JSON.stringify({ type: "joinGroup", group, ackId: this.ackId++ }));
  }

  join(group: string) {
    this.groups.add(group);
    this.sendJoin(group);
  }

  leave(group: string) {
    this.groups.delete(group);
    if (this.ws?.readyState === WebSocket.OPEN)
      this.ws.send(JSON.stringify({ type: "leaveGroup", group, ackId: this.ackId++ }));
  }

  on(h: Handler) {
    this.handlers.add(h);
    return () => this.handlers.delete(h);
  }

  stop() {
    this.stopped = true;
    this.ws?.close();
  }
}

function safeParse(s: string) {
  try {
    return JSON.parse(s);
  } catch {
    return s;
  }
}
