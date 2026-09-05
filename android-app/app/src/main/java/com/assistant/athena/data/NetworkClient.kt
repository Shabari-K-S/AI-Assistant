package com.assistant.athena.data

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class NetworkClient(private val context: Context) {

    companion object {
        private const val TAG = "Athena.Network"
        private const val PREFS_NAME = "athena_network_prefs"
        private const val KEY_BASE_URL = "base_url"
        const val DEFAULT_BASE_URL = "http://127.0.0.1:2027"

        @Volatile
        private var instance: NetworkClient? = null

        fun getInstance(context: Context): NetworkClient {
            return instance ?: synchronized(this) {
                instance ?: NetworkClient(context.applicationContext).also { instance = it }
            }
        }
    }

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    val okHttpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    var baseUrl: String
        get() = prefs.getString(KEY_BASE_URL, DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL
        set(value) {
            val clean = value.trim().removeSuffix("/")
            prefs.edit().putString(KEY_BASE_URL, clean).apply()
        }

    // =========================================================================
    // Generic HTTP Helpers
    // =========================================================================

    private suspend fun httpGet(path: String): String? = withContext(Dispatchers.IO) {
        try {
            val url = "$baseUrl$path"
            val request = Request.Builder().url(url).build()
            val response = okHttpClient.newCall(request).execute()
            val body = response.body?.string()
            response.close()
            body
        } catch (e: Exception) {
            Log.w(TAG, "GET $path failed: ${e.message}")
            null
        }
    }

    private suspend fun httpPostJson(path: String, payload: JSONObject): String? =
        withContext(Dispatchers.IO) {
            try {
                val url = "$baseUrl$path"
                val mediaType = "application/json; charset=utf-8".toMediaType()
                val requestBody = payload.toString().toRequestBody(mediaType)
                val request = Request.Builder().url(url).post(requestBody).build()
                val response = okHttpClient.newCall(request).execute()
                val body = response.body?.string()
                response.close()
                body
            } catch (e: Exception) {
                Log.w(TAG, "POST $path failed: ${e.message}")
                null
            }
        }

    // =========================================================================
    // Backend Health & State
    // =========================================================================

    suspend fun checkHealth(): Triple<Boolean, String, String> = withContext(Dispatchers.IO) {
        val raw = httpGet("/state") ?: return@withContext Triple(false, "offline", "Gemini 2.5 Flash")
        try {
            val json = JSONObject(raw)
            val online = json.optBoolean("online", false)
            val phase = json.optString("phase", "standby")
            val model = json.optString("llm_model", "Gemini 2.5 Flash")
            Triple(online, phase, model)
        } catch (_: Exception) {
            Triple(false, "offline", "Gemini 2.5 Flash")
        }
    }

    // =========================================================================
    // Multi-Session Conversation Management
    // =========================================================================

    suspend fun fetchSessions(): List<SessionItem> = withContext(Dispatchers.IO) {
        val raw = httpGet("/sessions") ?: return@withContext emptyList()
        try {
            val json = JSONObject(raw)
            val arr = json.optJSONArray("sessions") ?: return@withContext emptyList()
            val list = mutableListOf<SessionItem>()
            for (i in 0 until arr.length()) {
                val item = arr.optJSONObject(i) ?: continue
                list.add(SessionItem.fromJson(item))
            }
            list
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun fetchSessionDetail(sessionId: String): SessionDetail? = withContext(Dispatchers.IO) {
        val raw = httpGet("/sessions/detail?id=$sessionId") ?: return@withContext null
        try {
            val json = JSONObject(raw)
            val sObj = json.optJSONObject("session") ?: return@withContext null
            SessionDetail.fromJson(sObj)
        } catch (_: Exception) {
            null
        }
    }

    suspend fun createSession(title: String? = null): SessionItem? = withContext(Dispatchers.IO) {
        val payload = JSONObject()
        if (!title.isNullOrBlank()) payload.put("title", title)
        val raw = httpPostJson("/sessions/new", payload) ?: return@withContext null
        try {
            val json = JSONObject(raw)
            val sObj = json.optJSONObject("session") ?: return@withContext null
            SessionItem.fromJson(sObj)
        } catch (_: Exception) {
            null
        }
    }

    suspend fun renameSession(sessionId: String, newTitle: String): Boolean = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("id", sessionId).put("title", newTitle)
        val raw = httpPostJson("/sessions/rename", payload) ?: return@withContext false
        try {
            JSONObject(raw).optBoolean("ok", false)
        } catch (_: Exception) {
            false
        }
    }

    suspend fun deleteSession(sessionId: String): Boolean = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("id", sessionId)
        val raw = httpPostJson("/sessions/delete", payload) ?: return@withContext false
        try {
            JSONObject(raw).optBoolean("ok", false)
        } catch (_: Exception) {
            false
        }
    }

    suspend fun pinSession(sessionId: String): Boolean = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("id", sessionId)
        val raw = httpPostJson("/sessions/pin", payload) ?: return@withContext false
        try {
            JSONObject(raw).optBoolean("is_pinned", false)
        } catch (_: Exception) {
            false
        }
    }

    suspend fun sendPrompt(text: String, sessionId: String? = null): JSONObject? =
        withContext(Dispatchers.IO) {
            val payload = JSONObject().put("text", text)
            if (!sessionId.isNullOrBlank()) payload.put("session_id", sessionId)
            val raw = httpPostJson("/prompt", payload) ?: return@withContext null
            try {
                JSONObject(raw)
            } catch (_: Exception) {
                null
            }
        }

    suspend fun askAssistant(text: String, sessionId: String? = null): AskResult? =
        withContext(Dispatchers.IO) {
            val payload = JSONObject().put("text", text)
            if (!sessionId.isNullOrBlank()) payload.put("session_id", sessionId)
            val raw = httpPostJson("/ask", payload) ?: return@withContext null
            try {
                val json = JSONObject(raw)
                val reply = json.optString("reply", "")
                val sid = json.optString("session_id", sessionId ?: "")
                val ok = json.optBoolean("ok", true)
                val handledSlash = json.optBoolean("handled_slash", false)
                val toolDataJson = json.optJSONObject("tool_data")
                val toolData = ToolData.fromJson(toolDataJson)
                AskResult(
                    reply = reply,
                    sessionId = sid,
                    ok = ok,
                    handledSlash = handledSlash,
                    toolData = toolData
                )
            } catch (_: Exception) {
                null
            }
        }

    suspend fun askAssistantWithVision(
        text: String,
        imageB64: String,
        sessionId: String? = null
    ): AskResult? = withContext(Dispatchers.IO) {
        val payload = JSONObject()
            .put("text", text)
            .put("image_b64", imageB64)
        if (!sessionId.isNullOrBlank()) payload.put("session_id", sessionId)
        val raw = httpPostJson("/ask", payload) ?: return@withContext null
        try {
            val json = JSONObject(raw)
            val reply = json.optString("reply", "")
            val sid = json.optString("session_id", sessionId ?: "")
            val ok = json.optBoolean("ok", true)
            val handledSlash = json.optBoolean("handled_slash", false)
            val toolDataJson = json.optJSONObject("tool_data")
            val toolData = ToolData.fromJson(toolDataJson)
            AskResult(
                reply = reply,
                sessionId = sid,
                ok = ok,
                handledSlash = handledSlash,
                toolData = toolData
            )
        } catch (_: Exception) {
            null
        }
    }

    // =========================================================================
    // Markdown Notes Vault
    // =========================================================================

    suspend fun fetchNotes(): List<VaultNoteItem> = withContext(Dispatchers.IO) {
        val raw = httpGet("/notes") ?: return@withContext emptyList()
        try {
            val json = JSONObject(raw)
            val arr = json.optJSONArray("notes") ?: return@withContext emptyList()
            val list = mutableListOf<VaultNoteItem>()
            for (i in 0 until arr.length()) {
                val item = arr.optJSONObject(i) ?: continue
                list.add(VaultNoteItem.fromJson(item))
            }
            list
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun readNote(target: String): VaultNoteDetail? = withContext(Dispatchers.IO) {
        val encoded = java.net.URLEncoder.encode(target, "UTF-8")
        val raw = httpGet("/notes/read?target=$encoded") ?: return@withContext null
        try {
            val json = JSONObject(raw)
            if (json.optBoolean("ok", false)) {
                VaultNoteDetail.fromJson(json)
            } else null
        } catch (_: Exception) {
            null
        }
    }

    suspend fun saveNote(
        title: String,
        content: String,
        category: String,
        tags: List<String>,
        target: String? = null
    ): Boolean = withContext(Dispatchers.IO) {
        val payload = JSONObject()
            .put("title", title)
            .put("content", content)
            .put("category", category)
            .put("tags", JSONArray(tags))
        if (!target.isNullOrBlank()) {
            payload.put("target", target)
        }
        val raw = httpPostJson("/notes/save", payload) ?: return@withContext false
        try {
            JSONObject(raw).optBoolean("ok", false)
        } catch (_: Exception) {
            false
        }
    }

    suspend fun deleteNote(target: String): Boolean = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("target", target)
        val raw = httpPostJson("/notes/delete", payload) ?: return@withContext false
        try {
            JSONObject(raw).optBoolean("ok", false)
        } catch (_: Exception) {
            false
        }
    }

    // =========================================================================
    // Model Context Protocol (MCP) Ecosystem
    // =========================================================================

    suspend fun fetchMcpStatus(): Pair<List<McpServerConfig>, List<McpCatalogItem>> =
        withContext(Dispatchers.IO) {
            val raw = httpGet("/mcp") ?: return@withContext Pair(emptyList(), emptyList())
            try {
                val json = JSONObject(raw)
                val sArr = json.optJSONArray("servers") ?: JSONArray()
                val servers = mutableListOf<McpServerConfig>()
                for (i in 0 until sArr.length()) {
                    val sObj = sArr.optJSONObject(i) ?: continue
                    servers.add(McpServerConfig.fromJson(sObj))
                }

                val cArr = json.optJSONArray("catalog") ?: JSONArray()
                val catalog = mutableListOf<McpCatalogItem>()
                for (i in 0 until cArr.length()) {
                    val cObj = cArr.optJSONObject(i) ?: continue
                    catalog.add(McpCatalogItem.fromJson(cObj))
                }
                Pair(servers, catalog)
            } catch (_: Exception) {
                Pair(emptyList(), emptyList())
            }
        }

    suspend fun toggleMcpServer(name: String, enabled: Boolean): Boolean =
        withContext(Dispatchers.IO) {
            val payload = JSONObject().put("name", name).put("enabled", enabled)
            val raw = httpPostJson("/mcp/toggle", payload) ?: return@withContext false
            try {
                JSONObject(raw).optBoolean("ok", false)
            } catch (_: Exception) {
                false
            }
        }

    suspend fun restartMcpServer(name: String): Boolean = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("name", name)
        val raw = httpPostJson("/mcp/restart", payload) ?: return@withContext false
        try {
            JSONObject(raw).optBoolean("ok", false)
        } catch (_: Exception) {
            false
        }
    }

    suspend fun deleteMcpServer(name: String): Boolean = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("name", name)
        val raw = httpPostJson("/mcp/delete", payload) ?: return@withContext false
        try {
            JSONObject(raw).optBoolean("ok", false)
        } catch (_: Exception) {
            false
        }
    }

    suspend fun saveMcpServer(
        name: String,
        command: String,
        args: List<String>,
        env: Map<String, String>
    ): Boolean = withContext(Dispatchers.IO) {
        val envJson = JSONObject()
        env.forEach { (k, v) -> envJson.put(k, v) }
        val payload = JSONObject()
            .put("name", name)
            .put("command", command)
            .put("args", JSONArray(args))
            .put("env", envJson)
        val raw = httpPostJson("/mcp/save", payload) ?: return@withContext false
        try {
            JSONObject(raw).optBoolean("ok", false)
        } catch (_: Exception) {
            false
        }
    }

    suspend fun searchMcpEcosystem(query: String): JSONObject? = withContext(Dispatchers.IO) {
        val encoded = java.net.URLEncoder.encode(query, "UTF-8")
        val raw = httpGet("/mcp/search?q=$encoded") ?: return@withContext null
        try {
            JSONObject(raw)
        } catch (_: Exception) {
            null
        }
    }

    // =========================================================================
    // Skills, Agents, Timers, Briefing & Config
    // =========================================================================

    suspend fun fetchSkills(): List<AthenaSkill> = withContext(Dispatchers.IO) {
        val raw = httpGet("/skills") ?: return@withContext emptyList()
        try {
            val json = JSONObject(raw)
            val arr = json.optJSONArray("skills") ?: return@withContext emptyList()
            val list = mutableListOf<AthenaSkill>()
            for (i in 0 until arr.length()) {
                val obj = arr.optJSONObject(i) ?: continue
                list.add(AthenaSkill.fromJson(obj))
            }
            list
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun fetchAgents(): List<AthenaAgentProfile> = withContext(Dispatchers.IO) {
        val raw = httpGet("/agents") ?: return@withContext emptyList()
        try {
            val json = JSONObject(raw)
            val arr = json.optJSONArray("agents") ?: return@withContext emptyList()
            val list = mutableListOf<AthenaAgentProfile>()
            for (i in 0 until arr.length()) {
                val obj = arr.optJSONObject(i) ?: continue
                list.add(AthenaAgentProfile.fromJson(obj))
            }
            list
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun fetchTimers(): List<ActiveTimerItem> = withContext(Dispatchers.IO) {
        val raw = httpGet("/timers") ?: return@withContext emptyList()
        try {
            val json = JSONObject(raw)
            val arr = json.optJSONArray("timers") ?: return@withContext emptyList()
            val list = mutableListOf<ActiveTimerItem>()
            for (i in 0 until arr.length()) {
                val obj = arr.optJSONObject(i) ?: continue
                list.add(ActiveTimerItem.fromJson(obj))
            }
            list
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun createTimer(duration: String, label: String, timerType: String = "timer"): Boolean =
        withContext(Dispatchers.IO) {
            val payload = JSONObject()
                .put("duration", duration)
                .put("label", label)
                .put("type", timerType)
            val raw = httpPostJson("/timers/create", payload) ?: return@withContext false
            try {
                JSONObject(raw).optBoolean("ok", false)
            } catch (_: Exception) {
                false
            }
        }

    suspend fun cancelTimer(id: String): Boolean = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("id", id)
        val raw = httpPostJson("/timers/cancel", payload) ?: return@withContext false
        try {
            JSONObject(raw).optBoolean("ok", false)
        } catch (_: Exception) {
            false
        }
    }

    suspend fun fetchBriefing(type: String = "morning"): DailyBriefingData? =
        withContext(Dispatchers.IO) {
            val raw = httpGet("/briefing?type=$type") ?: return@withContext null
            try {
                val json = JSONObject(raw)
                if (json.optBoolean("ok", false)) {
                    DailyBriefingData.fromJson(json)
                } else null
            } catch (_: Exception) {
                null
            }
        }

    suspend fun updateConfig(threshold: Float? = null, muted: Boolean? = null): Boolean =
        withContext(Dispatchers.IO) {
            val payload = JSONObject()
            threshold?.let { payload.put("threshold", it.toDouble()) }
            muted?.let { payload.put("muted", it) }
            val raw = httpPostJson("/config", payload) ?: return@withContext false
            try {
                JSONObject(raw).optBoolean("ok", false)
            } catch (_: Exception) {
                false
            }
        }
}
