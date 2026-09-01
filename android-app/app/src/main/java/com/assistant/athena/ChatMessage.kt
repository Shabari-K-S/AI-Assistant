package com.assistant.athena

enum class SenderType {
    USER,
    ASSISTANT,
    SYSTEM
}

data class ChatMessage(
    val id: String = java.util.UUID.randomUUID().toString(),
    val sender: SenderType,
    var text: String,
    val timestamp: Long = System.currentTimeMillis(),
    val isStreaming: Boolean = false
)
