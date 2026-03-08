/** @odoo-module **/

import { Component, useState, useRef, onMounted, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MCPChatbot extends Component {
    static template = "mcp_odoo_connector.MCPChatbot";
    static props = {};

    setup() {
        this.rpc = useService("rpc");
        this.user = useService("user");
        this.notification = useService("notification");
        this.messagesRef = useRef("messagesContainer");

        this.state = useState({
            isOpen: false,
            isLoading: false,
            userInput: "",
            messages: [],
            sessionId: null,
            hasAccess: false,
        });

        // Check user access on mount
        this._checkAccess();
    }

    async _checkAccess() {
        try {
            const hasGroup = await this.user.hasGroup(
                "mcp_odoo_connector.group_mcp_user"
            );
            this.state.hasAccess = hasGroup;
        } catch {
            this.state.hasAccess = false;
        }
    }

    toggleChat() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen && this.state.messages.length === 0) {
            // Add welcome message
            this.state.messages.push({
                role: "assistant",
                content: "مرحباً! 👋 أنا مساعدك الذكي في Odoo. يمكنني مساعدتك في استعراض البيانات، إنشاء سجلات جديدة، تعديلها، أو حذفها. جرّب أن تقول: أنشئ جهة اتصال جديدة باسم أحمد محمد.",
                timestamp: this._now(),
            });
        }
        this._scrollToBottom();
    }

    closeChat() {
        this.state.isOpen = false;
    }

    onInputKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    onInputChange(ev) {
        this.state.userInput = ev.target.value;
    }

    async sendMessage() {
        const content = (this.state.userInput || "").trim();
        if (!content || this.state.isLoading) return;

        // Add user message
        this.state.messages.push({
            role: "user",
            content: content,
            timestamp: this._now(),
        });
        this.state.userInput = "";
        this.state.isLoading = true;
        this._scrollToBottom();

        try {
            const result = await this.rpc("/mcp/chatbot/send", {
                message: content,
                session_id: this.state.sessionId,
            });

            if (result.success) {
                this.state.sessionId = result.session_id;
                this.state.messages.push({
                    role: "assistant",
                    content: result.reply,
                    timestamp: this._now(),
                });
            } else {
                this.state.messages.push({
                    role: "assistant",
                    content: "⚠️ " + (result.error || "حدث خطأ أثناء الاتصال بالذكاء الاصطناعي."),
                    timestamp: this._now(),
                });
            }
        } catch (err) {
            this.state.messages.push({
                role: "assistant",
                content: "⚠️ تعذر الاتصال بالخادم. تأكد من تفعيل الشات في الإعدادات.",
                timestamp: this._now(),
            });
        }

        this.state.isLoading = false;
        this._scrollToBottom();
    }

    clearChat() {
        this.state.messages = [{
            role: "assistant",
            content: "تم مسح المحادثة. 🗑️ كيف يمكنني مساعدتك؟",
            timestamp: this._now(),
        }];
        this.state.sessionId = null;
    }

    _scrollToBottom() {
        setTimeout(() => {
            const container = this.messagesRef.el;
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }, 50);
    }

    _now() {
        return new Date().toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        });
    }

    formatMessage(content) {
        // Basic markdown-like formatting
        let html = content
            // Escape HTML
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            // Bold
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            // Italic
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            // Code blocks
            .replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
            // Inline code
            .replace(/`(.*?)`/g, "<code>$1</code>")
            // Line breaks
            .replace(/\n/g, "<br/>");
        return markup(html);
    }
}

registry.category("systray").add(
    "mcp_odoo_connector.chatbot",
    { Component: MCPChatbot },
    { sequence: 10 }
);
