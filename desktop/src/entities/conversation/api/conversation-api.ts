import { SOURCE, type RuntimeClient } from "../../../shared/api";
import type { Conversation, Message, Thread } from "../model/types";

/** Opening a thread, reading it, and saying one thing in it. */
export const conversationApi = {
  open(client: RuntimeClient, title = ""): Promise<Conversation> {
    return client.post<Conversation>("/api/conversations", { title });
  },

  thread(client: RuntimeClient, conversationId: string): Promise<Thread> {
    return client.get<Thread>(`/api/conversations/${conversationId}`);
  },

  /** Say one thing. It becomes an objective; Alethic decides what it takes. */
  send(client: RuntimeClient, conversationId: string, request: string): Promise<Message> {
    return client.post<Message>(`/api/conversations/${conversationId}/messages`, {
      request,
      source: SOURCE,
      input_type: "text",
    });
  },
};
