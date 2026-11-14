package org.earthcraft.mobilegundam

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var url: EditText
    private lateinit var session: EditText
    private lateinit var token: EditText
    private lateinit var status: TextView
    private val selectFile = 21

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("connection", MODE_PRIVATE)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24, 24, 24, 24) }
        url = field("HTTPS relay URL", prefs.getString("server", "") ?: "", root)
        session = field("Session ID", prefs.getString("session", "") ?: "", root)
        token = field("Phone token", prefs.getString("token", "") ?: "", root)
        status = TextView(this).apply { text = "Pair to send diagnostics and files to your development agent." }
        root.addView(status)
        button(root, "Save connection") {
            prefs.edit().putString("server", url.text.toString().trim())
                .putString("session", session.text.toString().trim())
                .putString("token", token.text.toString().trim()).apply()
            status.text = "Connection saved on device"
        }
        button(root, "Send diagnostic event") {
            bridge().event("device_feedback", "User triggered diagnostic report") { show(it) }
        }
        button(root, "Send document / APK / ZIP / screenshot") {
            startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                type = "*/*"; addCategory(Intent.CATEGORY_OPENABLE)
            }, selectFile)
        }
        setContentView(root)
        handleShare(intent)
    }

    private fun field(hint: String, value: String, root: LinearLayout): EditText = EditText(this).also {
        it.hint = hint; it.setSingleLine(true); it.setText(value)
        root.addView(it, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
    }
    private fun button(root: LinearLayout, label: String, callback: () -> Unit) {
        root.addView(Button(this).apply { text = label; setOnClickListener { callback() } })
    }
    private fun bridge() = MobileBridge(this, url.text.toString().trim(), session.text.toString().trim(), token.text.toString().trim())
    private fun show(result: String) = runOnUiThread { status.text = result }
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == selectFile && resultCode == RESULT_OK) {
            data?.data?.let { bridge().sendDocument(it) { output -> show(output) } }
        }
    }
    private fun handleShare(incoming: Intent?) {
        if (incoming?.action == Intent.ACTION_SEND) {
            @Suppress("DEPRECATION")
            val item = incoming.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
            item?.let { bridge().sendDocument(it) { output -> show(output) } }
        }
    }
}