import type { OpenIntentClient } from "./client.js";

export interface ResourceDefinition {
  uri: string;
  name: string;
  description: string;
  mimeType: string;
}

export interface ResourceTemplateDefinition {
  uriTemplate: string;
  name: string;
  description: string;
  mimeType: string;
}

export const RESOURCE_TEMPLATES: ResourceTemplateDefinition[] = [
  {
    uriTemplate: "openintent://intents",
    name: "All Intents",
    description: "List all intents. Append ?status=active to filter by status.",
    mimeType: "application/json",
  },
  {
    uriTemplate: "openintent://intents/{intent_id}",
    name: "Intent Details",
    description: "Get full details for a specific intent including status, state, and metadata.",
    mimeType: "application/json",
  },
  {
    uriTemplate: "openintent://intents/{intent_id}/events",
    name: "Intent Events",
    description: "Get the immutable event log for an intent.",
    mimeType: "application/json",
  },
  {
    uriTemplate: "openintent://intents/{intent_id}/state",
    name: "Intent State",
    description: "Get the current state key-value data for an intent.",
    mimeType: "application/json",
  },
  {
    uriTemplate: "openintent://channels/{channel_id}/messages",
    name: "Channel Messages",
    description: "Get messages from a messaging channel.",
    mimeType: "application/json",
  },
];

/**
 * Resolve a resource URI to data by calling the OpenIntent API.
 */
export async function handleReadResource(
  uri: string,
  client: OpenIntentClient,
): Promise<{ contents: Array<{ uri: string; mimeType: string; text: string }> }> {
  const parsed = new URL(uri);
  const path = parsed.hostname + parsed.pathname;

  // openintent://intents
  if (path === "intents" || path === "intents/") {
    const status = parsed.searchParams.get("status") ?? undefined;
    const data = await client.listIntents({ status });
    return {
      contents: [
        { uri, mimeType: "application/json", text: JSON.stringify(data, null, 2) },
      ],
    };
  }

  // openintent://intents/{id}/events
  const eventsMatch = path.match(/^intents\/([^/]+)\/events$/);
  if (eventsMatch) {
    const data = await client.getEvents({ intent_id: eventsMatch[1] });
    return {
      contents: [
        { uri, mimeType: "application/json", text: JSON.stringify(data, null, 2) },
      ],
    };
  }

  // openintent://intents/{id}/state
  const stateMatch = path.match(/^intents\/([^/]+)\/state$/);
  if (stateMatch) {
    const intent = (await client.getIntent(stateMatch[1])) as Record<string, unknown>;
    const state = intent.state ?? {};
    return {
      contents: [
        { uri, mimeType: "application/json", text: JSON.stringify(state, null, 2) },
      ],
    };
  }

  // openintent://intents/{id}
  const intentMatch = path.match(/^intents\/([^/]+)$/);
  if (intentMatch) {
    const data = await client.getIntent(intentMatch[1]);
    return {
      contents: [
        { uri, mimeType: "application/json", text: JSON.stringify(data, null, 2) },
      ],
    };
  }

  // openintent://channels/{id}/messages
  const channelMatch = path.match(/^channels\/([^/]+)\/messages$/);
  if (channelMatch) {
    const data = await client.getChannelMessages({ channel_id: channelMatch[1] });
    return {
      contents: [
        { uri, mimeType: "application/json", text: JSON.stringify(data, null, 2) },
      ],
    };
  }

  throw new Error(`Unknown resource URI: ${uri}`);
}
