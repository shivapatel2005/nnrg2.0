import { useState } from "react";
import { FaRobot, FaTimes, FaPaperPlane, FaPlus } from "react-icons/fa";

function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([
    {
      sender: "bot",
      text: "👋 Hello! Welcome to NNRG Institutions.\n\nAsk me anything about Admissions, Courses, Placements, Campus Facilities and Departments.",
    },
  ]);

  const handleSend = async () => {
    if (!message.trim()) return;

    const userMessage = message;

    // Show user's message
    setMessages((prev) => [
      ...prev,
      {
        sender: "user",
        text: userMessage,
      },
    ]);

    setMessage("");

   try {
    const response = await fetch(
      `http://127.0.0.1:8000/chat?prompt=${encodeURIComponent(userMessage)}`
    );

    const data = await response.json();

    // Show AI response
    setMessages((prev) => [
      ...prev,
      {
        sender: "bot",
        text: data.response,
      },
    ]);
  } catch (error) {
    setMessages((prev) => [
      ...prev,
      {
        sender: "bot",
        text: "❌ Unable to connect to the backend.",
      },
    ]);
  }
};

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="btn btn-primary rounded-circle position-fixed shadow"
          style={{
            bottom: "20px",
            right: "20px",
            width: "65px",
            height: "65px",
            fontSize: "28px",
            zIndex: 9999,
          }}
        >
          🤖
        </button>
      )}

      {open && (
        <div
          className="card shadow position-fixed"
          style={{
            bottom: "20px",
            right: "20px",
            width: "380px",
            height: "550px",
            borderRadius: "20px",
            zIndex: 9999,
          }}
        >
          {/* Header */}
          <div
            className="d-flex justify-content-between align-items-center p-3"
            style={{
              background: "#0d6efd",
              color: "white",
            }}
          >
            <div className="d-flex align-items-center">
              <FaRobot size={22} />
              <span className="ms-2 fw-bold">
                NNRG AI Assistant
              </span>
            </div>

            <FaTimes
              style={{ cursor: "pointer" }}
              onClick={() => setOpen(false)}
            />
          </div>

          {/* Chat Area */}

          <div
            className="p-3"
            style={{
              height: "420px",
              overflowY: "auto",
              background: "#f8f9fa",
            }}
          >
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`mb-3 ${
                  msg.sender === "user"
                    ? "text-end"
                    : "text-start"
                }`}
              >
                <div
                  className={`d-inline-block p-3 rounded ${
                    msg.sender === "user"
                      ? "bg-primary text-white"
                      : "bg-white shadow-sm"
                  }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}
          </div>

          {/* Bottom */}

          <div className="border-top p-2 d-flex align-items-center position-relative">

            {/* Plus */}

            <div className="position-relative me-2">

              <button
                className="btn btn-light"
                onClick={() => setShowMenu(!showMenu)}
              >
                <FaPlus />
              </button>

              {showMenu && (
                <div
                  className="card shadow position-absolute"
                  style={{
                    bottom: "55px",
                    left: "0",
                    width: "180px",
                    borderRadius: "12px",
                    zIndex: 10000,
                  }}
                >
                  <button
                    className="dropdown-item py-2"
                    onClick={() => {
                      setShowMenu(false);
                      alert("Upload PDF");
                    }}
                  >
                    📄 Upload PDF
                  </button>

                  <button
                    className="dropdown-item py-2"
                    onClick={() => {
                      setShowMenu(false);
                      alert("Website RAG");
                    }}
                  >
                    🌐 Website RAG
                  </button>
                </div>
              )}

            </div>

            {/* Input */}

            <input
              type="text"
              className="form-control"
              placeholder="Ask something..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSend();
                }
              }}
            />

            {/* Send */}

            <button
              className="btn btn-primary ms-2"
              onClick={handleSend}
            >
              <FaPaperPlane />
            </button>

          </div>

        </div>
      )}
    </>
  );
}

export default ChatWidget;