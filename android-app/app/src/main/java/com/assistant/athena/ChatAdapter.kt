package com.assistant.athena

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Build
import android.text.Html
import android.text.Spanned
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.recyclerview.widget.RecyclerView

class ChatAdapter(
    private val context: Context,
    private val onSpeakClicked: (String) -> Unit
) : RecyclerView.Adapter<ChatAdapter.ChatViewHolder>() {

    private val messages = mutableListOf<ChatMessage>()

    fun setMessages(newMessages: List<ChatMessage>) {
        messages.clear()
        messages.addAll(newMessages)
        notifyDataSetChanged()
    }

    fun addMessage(message: ChatMessage) {
        messages.add(message)
        notifyItemInserted(messages.size - 1)
    }

    fun updateLastAssistantMessage(text: String) {
        val lastIdx = messages.indexOfLast { it.sender == SenderType.ASSISTANT }
        if (lastIdx != -1) {
            messages[lastIdx].text = text
            notifyItemChanged(lastIdx)
        } else {
            addMessage(ChatMessage(sender = SenderType.ASSISTANT, text = text))
        }
    }

    fun updateLastSystemMessage(text: String) {
        val lastIdx = messages.indexOfLast { it.sender == SenderType.SYSTEM }
        if (lastIdx != -1) {
            messages[lastIdx].text = text
            notifyItemChanged(lastIdx)
        } else {
            addMessage(ChatMessage(sender = SenderType.SYSTEM, text = text))
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ChatViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_chat_message, parent, false)
        return ChatViewHolder(view)
    }

    override fun onBindViewHolder(holder: ChatViewHolder, position: Int) {
        val msg = messages[position]
        holder.bind(msg)
    }

    override fun getItemCount(): Int = messages.size

    inner class ChatViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val layoutUser: LinearLayout = itemView.findViewById(R.id.layoutUserContainer)
        private val txtUserContent: TextView = itemView.findViewById(R.id.txtUserContent)

        private val layoutAssistant: LinearLayout = itemView.findViewById(R.id.layoutAssistantContainer)
        private val txtAssistantContent: TextView = itemView.findViewById(R.id.txtAssistantContent)
        private val btnCopy: ImageButton = itemView.findViewById(R.id.btnItemCopy)
        private val btnSpeak: ImageButton = itemView.findViewById(R.id.btnItemSpeak)

        private val layoutSystem: LinearLayout = itemView.findViewById(R.id.layoutSystemContainer)
        private val txtSystemContent: TextView = itemView.findViewById(R.id.txtSystemContent)

        fun bind(message: ChatMessage) {
            layoutUser.visibility = View.GONE
            layoutAssistant.visibility = View.GONE
            layoutSystem.visibility = View.GONE

            when (message.sender) {
                SenderType.USER -> {
                    layoutUser.visibility = View.VISIBLE
                    txtUserContent.text = message.text
                }
                SenderType.ASSISTANT -> {
                    layoutAssistant.visibility = View.VISIBLE
                    txtAssistantContent.text = formatHtml(formatMarkdown(message.text))

                    btnCopy.setOnClickListener {
                        val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        cm.setPrimaryClip(ClipData.newPlainText("ATHENA Reply", message.text))
                        Toast.makeText(context, "Copied to clipboard", Toast.LENGTH_SHORT).show()
                    }

                    btnSpeak.setOnClickListener {
                        onSpeakClicked(message.text)
                    }
                }
                SenderType.SYSTEM -> {
                    layoutSystem.visibility = View.VISIBLE
                    txtSystemContent.text = formatHtml(message.text)
                }
            }
        }

        private fun formatMarkdown(text: String): String {
            return text
                .replace(Regex("\\*\\*(.*?)\\*\\*"), "<b>$1</b>")
                .replace(Regex("`([^`]+)`"), "<tt>$1</tt>")
                .replace("\n", "<br/>")
        }

        private fun formatHtml(html: String): Spanned {
            return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                Html.fromHtml(html, Html.FROM_HTML_MODE_COMPACT)
            } else {
                @Suppress("DEPRECATION")
                Html.fromHtml(html)
            }
        }
    }
}
