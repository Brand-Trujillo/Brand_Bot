package com.brandbot.webview

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.os.Bundle
import android.text.InputType
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.view.View
import android.widget.EditText
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.dialog.MaterialAlertDialogBuilder

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var errorText: TextView
    private lateinit var toolbar: MaterialToolbar

    private val prefs by lazy { getSharedPreferences("brandbot_prefs", MODE_PRIVATE) }

    companion object {
        private const val PREF_CHATBOT_URL = "chatbot_url"
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        toolbar = findViewById(R.id.toolbar)
        toolbar.title = getString(R.string.brand_title)
        toolbar.subtitle = getString(R.string.brand_subtitle)
        toolbar.setOnLongClickListener {
            promptForChatbotUrl(force = false)
            true
        }

        webView = findViewById(R.id.webview)
        errorText = findViewById(R.id.error_text)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        }

        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                errorText.visibility = View.GONE
                super.onPageStarted(view, url, favicon)
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                if (request?.isForMainFrame == true) {
                    errorText.text = getString(R.string.connection_error)
                    errorText.visibility = View.VISIBLE
                }
                super.onReceivedError(view, request, error)
            }
        }

        val configuredUrl = getConfiguredChatbotUrl()
        if (isValidChatbotUrl(configuredUrl)) {
            loadChatbot(configuredUrl)
        } else {
            promptForChatbotUrl(force = true)
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack()
                } else {
                    finish()
                }
            }
        })
    }

    override fun onDestroy() {
        webView.destroy()
        super.onDestroy()
    }

    private fun getConfiguredChatbotUrl(): String {
        val saved = prefs.getString(PREF_CHATBOT_URL, "")?.trim().orEmpty()
        if (saved.isNotEmpty()) return saved
        return BuildConfig.CHATBOT_URL.trim()
    }

    private fun isValidChatbotUrl(url: String): Boolean {
        if (url.isBlank()) return false
        if (url.contains("TU_URL_PUBLICA_AQUI", ignoreCase = true)) return false
        if (url.contains("tu_url_publica_aqui", ignoreCase = true)) return false
        return url.startsWith("http://") || url.startsWith("https://")
    }

    private fun loadChatbot(url: String) {
        errorText.visibility = View.GONE
        webView.loadUrl(url)
    }

    private fun promptForChatbotUrl(force: Boolean) {
        val input = EditText(this).apply {
            hint = getString(R.string.url_hint)
            setText(getConfiguredChatbotUrl().replace("TU_URL_PUBLICA_AQUI", "").replace("tu_url_publica_aqui", ""))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
        }

        val dialog = MaterialAlertDialogBuilder(this)
            .setTitle(R.string.url_dialog_title)
            .setMessage(R.string.url_dialog_message)
            .setView(input)
            .setCancelable(!force)
            .setPositiveButton(R.string.save_label) { _, _ ->
                val entered = input.text?.toString()?.trim().orEmpty()
                if (isValidChatbotUrl(entered)) {
                    prefs.edit().putString(PREF_CHATBOT_URL, entered).apply()
                    loadChatbot(entered)
                } else {
                    errorText.text = getString(R.string.invalid_url_error)
                    errorText.visibility = View.VISIBLE
                    if (force) {
                        promptForChatbotUrl(force = true)
                    }
                }
            }

        if (!force) {
            dialog.setNegativeButton(R.string.cancel_label, null)
        }

        dialog.show()
    }
}
