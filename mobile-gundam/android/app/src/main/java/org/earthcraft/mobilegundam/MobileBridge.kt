package org.earthcraft.mobilegundam

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.concurrent.Executors

/** Opt-in phone-side transport for explicit documents and app-provided diagnostics. */
class MobileBridge(private val context: Context, private val server: String,
                   private val session: String, private val phoneToken: String) {
    private val worker = Executors.newSingleThreadExecutor()
    private val maxBytes = 256L * 1024 * 1024

    fun event(kind: String, details: String, onResult: (String) -> Unit) {
        worker.execute {
            try {
                val body = JSONObject().put("kind", kind).put("message", details).toString()
                onResult(send("events", body.toByteArray(Charsets.UTF_8), "application/json"))
            } catch (ex: Exception) { onResult("ERROR: ${ex.message}") }
        }
    }

    fun sendDocument(uri: Uri, onResult: (String) -> Unit) {
        worker.execute {
            var temp: File? = null
            try {
                temp = File.createTempFile("gundam-", ".upload", context.cacheDir)
                var size = 0L
                val input = context.contentResolver.openInputStream(uri) ?: throw IOException("Cannot open file")
                input.use { source -> temp!!.outputStream().use { out ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val count = source.read(buffer)
                        if (count < 0) break
                        size += count
                        if (size > maxBytes) throw IOException("File exceeds 256 MB")
                        out.write(buffer, 0, count)
                    }
                } }
                onResult(sendFile(temp!!, queryName(uri)))
            } catch (ex: Exception) { onResult("ERROR: ${ex.message}") }
            finally { temp?.delete() }
        }
    }

    fun diagnosticsFromAppFile(file: File, onResult: (String) -> Unit) {
        worker.execute {
            try {
                if (!file.canonicalPath.startsWith(context.filesDir.canonicalPath + File.separator)) {
                    throw IOException("Configured app-private files only")
                }
                onResult(sendFile(file, file.name))
            } catch (ex: Exception) { onResult("ERROR: ${ex.message}") }
        }
    }

    private fun queryName(uri: Uri): String {
        var name = "document"
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) name = cursor.getString(0) ?: name
        }
        return name
    }

    private fun connection(route: String): HttpURLConnection {
        if (!server.startsWith("https://")) throw IOException("An HTTPS relay URL is required")
        if (!Regex("[0-9a-f]{24}").matches(session)) throw IOException("Invalid session ID")
        return (URL("${server.trimEnd('/')}/v1/s/$session/$route").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 15000
            readTimeout = 60000
            setRequestProperty("Authorization", "Bearer $phoneToken")
            doOutput = true
        }
    }

    private fun result(conn: HttpURLConnection): String {
        val status = conn.responseCode
        val body = (if (status in 200..299) conn.inputStream else conn.errorStream)
            ?.bufferedReader()?.use { it.readText() } ?: ""
        if (status !in 200..299) throw IOException("HTTP $status: $body")
        return body
    }

    private fun send(route: String, bytes: ByteArray, mime: String): String {
        val conn = connection(route)
        try {
            conn.setRequestProperty("Content-Type", mime)
            conn.setFixedLengthStreamingMode(bytes.size)
            conn.outputStream.use { it.write(bytes) }
            return result(conn)
        } finally { conn.disconnect() }
    }

    private fun sendFile(file: File, name: String): String {
        if (file.length() > maxBytes) throw IOException("File exceeds 256 MB")
        val conn = connection("files")
        try {
            conn.setRequestProperty("Content-Type", "application/octet-stream")
            conn.setRequestProperty("X-File-Name", URLEncoder.encode(name, "UTF-8").replace("+", "%20"))
            conn.setFixedLengthStreamingMode(file.length())
            conn.outputStream.use { out -> file.inputStream().use { it.copyTo(out, 64 * 1024) } }
            return result(conn)
        } finally { conn.disconnect() }
    }
}