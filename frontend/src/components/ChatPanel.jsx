import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";

const EXAMPLE_QUERIES = [
  "Which products have the most billing documents?",
  "Trace the full flow of billing document 90504298",
  "Show sales orders delivered but never billed",
  "Which customers have the most incomplete order flows?",
  "What is the average payment delay across all invoices?",
];

export default function ChatPanel({ apiUrl, onHighlight }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState("");
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || isStreaming) return;

    setInput("");
    setIsStreaming(true);
    setStatus("");

    // Add user message
    const userMsg = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);

    // Add placeholder for assistant
    const assistantMsg = { role: "assistant", content: "", nodeIds: [] };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const response = await fetch(`${apiUrl}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let fullContent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            const eventType = line.slice(7).trim();
            continue;
          }

          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              if (
                data.content !== undefined &&
                typeof data.content === "string" &&
                data.content
              ) {
                fullContent += data.content;
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last && last.role === "assistant") {
                    updated[updated.length - 1] = {
                      ...last,
                      content: fullContent,
                    };
                  }
                  return updated;
                });
              }

              if (data.node_ids) {
                const nodeIds = data.node_ids;
                onHighlight(nodeIds);
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last && last.role === "assistant") {
                    updated[updated.length - 1] = { ...last, nodeIds };
                  }
                  return updated;
                });
              }

              if (
                data.content !== undefined &&
                typeof data.content === "string" &&
                !data.node_ids
              ) {
                // Status or token — handled above
              }
            } catch (e) {
              // not JSON, skip
            }
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last && last.role === "assistant") {
          updated[updated.length - 1] = {
            ...last,
            content: `Error: ${err.message}. Is the backend running?`,
          };
        }
        return updated;
      });
    }

    setIsStreaming(false);
    setStatus("");
  }, [input, isStreaming, apiUrl, onHighlight]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClear = () => {
    setMessages([]);
    onHighlight([]);
  };

  const handleExampleClick = (query) => {
    setInput(query);
    inputRef.current?.focus();
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2 bg-slate-800/90 backdrop-blur border-b border-slate-700 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-emerald-400 tracking-wide">
            💬 QUERY ASSISTANT
          </h2>
          <p className="text-xs text-slate-400">
            Ask questions about the supply chain dataset
          </p>
        </div>
        <button
          onClick={handleClear}
          className="text-xs px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 transition"
        >
          Clear
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="space-y-3 mt-4">
            <p className="text-xs text-slate-500 text-center">
              Try one of these example queries:
            </p>
            <div className="space-y-2">
              {EXAMPLE_QUERIES.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleExampleClick(q)}
                  className="w-full text-left text-xs px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 hover:border-slate-500 transition"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] px-3 py-2 rounded-lg text-sm chat-message ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-br-sm"
                  : "bg-slate-800 text-slate-200 border border-slate-700 rounded-bl-sm"
              }`}
            >
              {msg.role === "assistant" ? (
                <div>
                  <ReactMarkdown>{msg.content || "..."}</ReactMarkdown>
                  {msg.nodeIds && msg.nodeIds.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-slate-700">
                      <span className="text-[10px] uppercase text-slate-500">
                        {msg.nodeIds.length} nodes highlighted in graph
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {isStreaming && status && (
          <div className="text-xs text-slate-500 italic">{status}</div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-slate-700 bg-slate-800/50">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about orders, deliveries, invoices, payments..."
            rows={1}
            className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none"
            disabled={isStreaming}
          />
          <button
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            type="button"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition"
          >
            {isStreaming ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
