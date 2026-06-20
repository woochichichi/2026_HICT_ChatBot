/**
 * 공용 마크다운 렌더러 — 답변 가독성(목록/볼드/개행)을 일관되게 표시.
 * 사용: 응대 모드 답변 말풍선, 오답 제보 모달 미리보기, 제보 검토 카드.
 * (raw 마크다운 텍스트가 그대로 노출되지 않도록 모든 답변 표시 지점에서 사용)
 */
import ReactMarkdown from "react-markdown";

export default function Markdown({ content }) {
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p style={{ margin: "7px 0", lineHeight: 1.72 }}>{children}</p>,
        strong: ({ children }) => <strong style={{ fontWeight: 700, color: "var(--navy)" }}>{children}</strong>,
        ul: ({ children }) => <ul style={{ margin: "8px 0", paddingLeft: 20 }}>{children}</ul>,
        ol: ({ children }) => <ol style={{ margin: "8px 0", paddingLeft: 22 }}>{children}</ol>,
        li: ({ children }) => <li style={{ margin: "5px 0", lineHeight: 1.66, paddingLeft: 2 }}>{children}</li>,
        h1: ({ children }) => <h3 style={{ fontSize: 16, fontWeight: 700, margin: "10px 0 5px", color: "var(--navy)" }}>{children}</h3>,
        h2: ({ children }) => <h3 style={{ fontSize: 15, fontWeight: 700, margin: "10px 0 5px", color: "var(--navy)" }}>{children}</h3>,
        h3: ({ children }) => <h4 style={{ fontSize: 14.5, fontWeight: 600, margin: "8px 0 4px", color: "var(--navy)" }}>{children}</h4>,
        code: ({ children }) => (
          <code style={{ background: "#eef1f6", borderRadius: 4, padding: "1px 5px", fontSize: 13 }}>{children}</code>
        ),
        hr: () => <hr style={{ border: "none", borderTop: "1px solid var(--line)", margin: "10px 0" }} />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
