package com.assistant.athena.data

import org.json.JSONArray
import org.json.JSONObject

// =========================================================================
// 1. Session & Multi-Conversation Models
// =========================================================================

data class SessionItem(
    val id: String,
    val title: String,
    val createdAt: Double,
    val updatedAt: Double,
    val isPinned: Boolean,
    val messageCount: Int,
    val lastMessage: String,
    val lastRole: String
) {
    companion object {
        fun fromJson(json: JSONObject): SessionItem {
            return SessionItem(
                id = json.optString("id", ""),
                title = json.optString("title", "Untitled Session"),
                createdAt = json.optDouble("created_at", 0.0),
                updatedAt = json.optDouble("updated_at", 0.0),
                isPinned = json.optBoolean("is_pinned", false),
                messageCount = json.optInt("message_count", 0),
                lastMessage = json.optString("last_message", ""),
                lastRole = json.optString("last_role", "assistant")
            )
        }
    }
}

data class SessionDetail(
    val id: String,
    val title: String,
    val createdAt: Double,
    val updatedAt: Double,
    val isPinned: Boolean,
    val messages: List<MessageItem>
) {
    companion object {
        fun fromJson(json: JSONObject): SessionDetail {
            val msgs = mutableListOf<MessageItem>()
            val arr = json.optJSONArray("messages") ?: JSONArray()
            for (i in 0 until arr.length()) {
                val mJson = arr.optJSONObject(i) ?: continue
                msgs.add(MessageItem.fromJson(mJson))
            }
            return SessionDetail(
                id = json.optString("id", ""),
                title = json.optString("title", ""),
                createdAt = json.optDouble("created_at", 0.0),
                updatedAt = json.optDouble("updated_at", 0.0),
                isPinned = json.optBoolean("is_pinned", false),
                messages = msgs
            )
        }
    }
}

data class ToolData(
    val name: String,
    val durationMs: Double = 0.0,
    val status: String = "ok",
    val preview: String = ""
) {
    companion object {
        fun fromJson(json: JSONObject?): ToolData? {
            if (json == null) return null
            return ToolData(
                name = json.optString("name", "tool"),
                durationMs = json.optDouble("duration_ms", 0.0),
                status = json.optString("status", "ok"),
                preview = json.optString("preview", "")
            )
        }
    }
}

data class MessageItem(
    val id: String,
    val role: String, // "user" | "assistant" | "system" | "tool"
    val text: String,
    val timestamp: Double,
    val toolData: ToolData? = null
) {
    companion object {
        fun fromJson(json: JSONObject): MessageItem {
            val toolJson = json.optJSONObject("tool_data")
            return MessageItem(
                id = json.optString("id", java.util.UUID.randomUUID().toString()),
                role = json.optString("role", "assistant"),
                text = json.optString("text", ""),
                timestamp = json.optDouble("timestamp", System.currentTimeMillis() / 1000.0),
                toolData = ToolData.fromJson(toolJson)
            )
        }
    }
}

data class AskResult(
    val reply: String,
    val sessionId: String,
    val ok: Boolean = true,
    val handledSlash: Boolean = false
)

// =========================================================================
// 2. Markdown Notes Vault Models
// =========================================================================

data class VaultNoteItem(
    val id: String,
    val title: String,
    val category: String,
    val path: String,
    val createdAt: String,
    val updatedAt: String? = null,
    val preview: String = "",
    val tags: List<String> = emptyList(),
    val sourcesCount: Int? = null,
    val modelUsed: String? = null,
    val severity: String? = null
) {
    companion object {
        fun fromJson(json: JSONObject): VaultNoteItem {
            val tagList = mutableListOf<String>()
            val tagsArr = json.optJSONArray("tags")
            if (tagsArr != null) {
                for (i in 0 until tagsArr.length()) {
                    tagList.add(tagsArr.optString(i))
                }
            }
            return VaultNoteItem(
                id = json.optString("id", ""),
                title = json.optString("title", "Untitled Note"),
                category = json.optString("category", "general"),
                path = json.optString("path", ""),
                createdAt = json.optString("created_at", ""),
                updatedAt = json.optString("updated_at", null),
                preview = json.optString("preview", ""),
                tags = tagList,
                sourcesCount = if (json.has("sources_count")) json.optInt("sources_count") else null,
                modelUsed = json.optString("model_used", null),
                severity = json.optString("severity", null)
            )
        }
    }
}

data class VaultNoteDetail(
    val id: String,
    val title: String,
    val category: String,
    val path: String,
    val createdAt: String,
    val updatedAt: String? = null,
    val tags: List<String> = emptyList(),
    val content: String = ""
) {
    companion object {
        fun fromJson(json: JSONObject): VaultNoteDetail {
            val tagList = mutableListOf<String>()
            val tagsArr = json.optJSONArray("tags")
            if (tagsArr != null) {
                for (i in 0 until tagsArr.length()) {
                    tagList.add(tagsArr.optString(i))
                }
            }
            return VaultNoteDetail(
                id = json.optString("id", ""),
                title = json.optString("title", "Untitled Note"),
                category = json.optString("category", "general"),
                path = json.optString("path", ""),
                createdAt = json.optString("created_at", ""),
                updatedAt = json.optString("updated_at", null),
                tags = tagList,
                content = json.optString("content", "")
            )
        }
    }
}

// =========================================================================
// 3. Model Context Protocol (MCP) Models
// =========================================================================

data class McpTool(
    val name: String,
    val description: String = "",
    val parametersCount: Int = 0
) {
    companion object {
        fun fromJson(json: JSONObject): McpTool {
            val schema = json.optJSONObject("inputSchema")
            val props = schema?.optJSONObject("properties")
            val pCount = props?.length() ?: 0
            return McpTool(
                name = json.optString("name", "tool"),
                description = json.optString("description", ""),
                parametersCount = pCount
            )
        }
    }
}

data class McpServerConfig(
    val name: String,
    val command: String,
    val args: List<String>,
    val enabled: Boolean,
    val running: Boolean,
    val toolsCount: Int,
    val tools: List<McpTool> = emptyList(),
    val error: String? = null
) {
    companion object {
        fun fromJson(json: JSONObject): McpServerConfig {
            val argList = mutableListOf<String>()
            val argsArr = json.optJSONArray("args")
            if (argsArr != null) {
                for (i in 0 until argsArr.length()) {
                    argList.add(argsArr.optString(i))
                }
            }
            val toolList = mutableListOf<McpTool>()
            val toolsArr = json.optJSONArray("tools")
            if (toolsArr != null) {
                for (i in 0 until toolsArr.length()) {
                    val tObj = toolsArr.optJSONObject(i) ?: continue
                    toolList.add(McpTool.fromJson(tObj))
                }
            }
            return McpServerConfig(
                name = json.optString("name", ""),
                command = json.optString("command", ""),
                args = argList,
                enabled = json.optBoolean("enabled", true),
                running = json.optBoolean("running", false),
                toolsCount = json.optInt("tools_count", toolList.size),
                tools = toolList,
                error = json.optString("error", null)
            )
        }
    }
}

data class McpCatalogItem(
    val id: String,
    val name: String,
    val description: String,
    val category: String,
    val icon: String,
    val command: String,
    val args: List<String>,
    val preinstalled: Boolean
) {
    companion object {
        fun fromJson(json: JSONObject): McpCatalogItem {
            val argList = mutableListOf<String>()
            val argsArr = json.optJSONArray("args")
            if (argsArr != null) {
                for (i in 0 until argsArr.length()) {
                    argList.add(argsArr.optString(i))
                }
            }
            return McpCatalogItem(
                id = json.optString("id", ""),
                name = json.optString("name", ""),
                description = json.optString("description", ""),
                category = json.optString("category", "utilities"),
                icon = json.optString("icon", "Terminal"),
                command = json.optString("command", ""),
                args = argList,
                preinstalled = json.optBoolean("preinstalled", false)
            )
        }
    }
}

// =========================================================================
// 4. Skills, Agents, Timers, Briefing Models
// =========================================================================

data class AthenaSkill(
    val name: String,
    val description: String,
    val category: String,
    val triggers: List<String> = emptyList(),
    val instructions: String = ""
) {
    companion object {
        fun fromJson(json: JSONObject): AthenaSkill {
            val trigList = mutableListOf<String>()
            val trigArr = json.optJSONArray("triggers")
            if (trigArr != null) {
                for (i in 0 until trigArr.length()) {
                    trigList.add(trigArr.optString(i))
                }
            }
            return AthenaSkill(
                name = json.optString("name", ""),
                description = json.optString("description", ""),
                category = json.optString("category", "core"),
                triggers = trigList,
                instructions = json.optString("instructions", "")
            )
        }
    }
}

data class AthenaAgentProfile(
    val name: String,
    val role: String,
    val description: String,
    val category: String,
    val allowedTools: List<String> = emptyList()
) {
    companion object {
        fun fromJson(json: JSONObject): AthenaAgentProfile {
            val toolList = mutableListOf<String>()
            val toolArr = json.optJSONArray("allowed_tools")
            if (toolArr != null) {
                for (i in 0 until toolArr.length()) {
                    toolList.add(toolArr.optString(i))
                }
            }
            return AthenaAgentProfile(
                name = json.optString("name", ""),
                role = json.optString("role", ""),
                description = json.optString("description", ""),
                category = json.optString("category", "specialist"),
                allowedTools = toolList
            )
        }
    }
}

data class ActiveTimerItem(
    val id: String,
    val label: String,
    val timerType: String,
    val totalSeconds: Int,
    val remainingSeconds: Int,
    val progressPercent: Double,
    val status: String
) {
    companion object {
        fun fromJson(json: JSONObject): ActiveTimerItem {
            return ActiveTimerItem(
                id = json.optString("id", ""),
                label = json.optString("label", "Timer"),
                timerType = json.optString("timer_type", "timer"),
                totalSeconds = json.optInt("total_seconds", 0),
                remainingSeconds = json.optInt("remaining_seconds", 0),
                progressPercent = json.optDouble("progress_percent", 0.0),
                status = json.optString("status", "running")
            )
        }
    }
}

data class DailyBriefingData(
    val date: String,
    val city: String,
    val tempC: Double,
    val weatherCondition: String,
    val pendingTodosCount: Int,
    val pendingTodos: List<String>,
    val spokenSummary: String,
    val markdownReport: String
) {
    companion object {
        fun fromJson(json: JSONObject): DailyBriefingData {
            val w = json.optJSONObject("weather")
            val t = json.optJSONObject("todos")
            val todosList = mutableListOf<String>()
            val pendingArr = t?.optJSONArray("pending")
            if (pendingArr != null) {
                for (i in 0 until pendingArr.length()) {
                    todosList.add(pendingArr.optString(i))
                }
            }
            return DailyBriefingData(
                date = json.optString("date", ""),
                city = w?.optString("city", "Unknown") ?: "Unknown",
                tempC = w?.optDouble("temp_c", 22.0) ?: 22.0,
                weatherCondition = w?.optString("condition", "Clear") ?: "Clear",
                pendingTodosCount = t?.optInt("pending_count", 0) ?: 0,
                pendingTodos = todosList,
                spokenSummary = json.optString("spoken_summary", ""),
                markdownReport = json.optString("markdown_report", "")
            )
        }
    }
}
