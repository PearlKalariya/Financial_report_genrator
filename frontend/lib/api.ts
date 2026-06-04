export type StreamEvent =
  | {
      type: "status";
      agent?: string;
      message?: string;
    }
  | {
      type: "section";
      title?: string;
    }
  | {
      type: "delta";
      content?: string;
    }
  | {
      type: "citation";
      title?: string;
      url?: string;
    }
  | {
      type: "done";
      message?: string;
    }
  | {
      type: "error";
      message?: string;
    };

export async function streamQuery(
  query: string,
  sessionId: string,
  onEvent: (event: StreamEvent) => void
) {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  const response = await fetch(`${apiBaseUrl}/api/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query, session_id: sessionId })
  });

  if (!response.ok || !response.body) {
    throw new Error(`Unable to start research stream. API returned ${response.status}.`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .find((item) => item.startsWith("data: "));

      if (!line) {
        continue;
      }

      onEvent(JSON.parse(line.replace("data: ", "")) as StreamEvent);
    }
  }
}
