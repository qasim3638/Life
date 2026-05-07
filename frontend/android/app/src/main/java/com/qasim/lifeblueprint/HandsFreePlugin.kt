package com.qasim.lifeblueprint

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.Permission
import com.getcapacitor.annotation.PermissionCallback

/**
 * HandsFreePlugin — Capacitor bridge to HandsFreeService.
 *
 * JS API:
 *   - HandsFree.start({accessKey, keywordPath, porcupineModelPath, ...}) → starts service
 *   - HandsFree.stop()  → stops service
 *   - HandsFree.isRunning() → bool
 *   - listenerHandle.addListener('wake', cb) → fires when wake word detected
 *
 * Model files MUST be copied to filesDir before passing paths in. The JS
 * helper `nativeBridge.js` handles that on first start using fetch + fs.
 */
@CapacitorPlugin(
    name = "HandsFree",
    permissions = [
        Permission(
            alias = "microphone",
            strings = [Manifest.permission.RECORD_AUDIO],
        ),
        Permission(
            alias = "notifications",
            strings = [Manifest.permission.POST_NOTIFICATIONS],
        ),
    ],
)
class HandsFreePlugin : Plugin() {

    private var receiver: BroadcastReceiver? = null
    private var pendingStart: PluginCall? = null

    override fun load() {
        super.load()
        receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent?.action == HandsFreeService.ACTION_WAKE) {
                    notifyListeners("wake", JSObject().put("source", "handsfree"))
                }
            }
        }
        val filter = IntentFilter(HandsFreeService.ACTION_WAKE)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            context.registerReceiver(receiver, filter)
        }
    }

    override fun handleOnDestroy() {
        try { context.unregisterReceiver(receiver) } catch (_: Exception) {}
        super.handleOnDestroy()
    }

    @PluginMethod
    fun start(call: PluginCall) {
        if (!hasMicPermission()) {
            pendingStart = call
            requestPermissionForAlias("microphone", call, "micPermissionCallback")
            return
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !hasNotificationPermission()) {
            pendingStart = call
            requestPermissionForAlias("notifications", call, "notificationsPermissionCallback")
            return
        }
        beginService(call)
    }

    @PermissionCallback
    private fun micPermissionCallback(call: PluginCall) {
        if (!hasMicPermission()) {
            call.reject("Microphone permission denied")
            return
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !hasNotificationPermission()) {
            requestPermissionForAlias("notifications", call, "notificationsPermissionCallback")
            return
        }
        beginService(call)
    }

    @PermissionCallback
    private fun notificationsPermissionCallback(call: PluginCall) {
        beginService(call)
    }

    private fun beginService(call: PluginCall) {
        val accessKey = call.getString("accessKey") ?: ""
        val keywordPath = call.getString("keywordPath") ?: ""
        val porcupineModelPath = call.getString("porcupineModelPath") ?: ""
        val eagleModelPath = call.getString("eagleModelPath")
        val profileBase64 = call.getString("profileBase64")
        val threshold = call.getFloat("threshold", 0.6f) ?: 0.6f

        if (accessKey.isBlank() || keywordPath.isBlank() || porcupineModelPath.isBlank()) {
            call.reject("accessKey, keywordPath, porcupineModelPath required")
            return
        }
        val intent = Intent(context, HandsFreeService::class.java).apply {
            putExtra("accessKey", accessKey)
            putExtra("keywordPath", keywordPath)
            putExtra("porcupineModelPath", porcupineModelPath)
            putExtra("eagleModelPath", eagleModelPath)
            putExtra("profileBase64", profileBase64)
            putExtra("threshold", threshold)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent)
        } else {
            context.startService(intent)
        }
        call.resolve(JSObject().put("started", true))
    }

    @PluginMethod
    fun stop(call: PluginCall) {
        context.stopService(Intent(context, HandsFreeService::class.java))
        call.resolve(JSObject().put("stopped", true))
    }

    @PluginMethod
    fun isRunning(call: PluginCall) {
        // Best-effort — Android doesn't expose a clean way; we rely on app
        // tracking on JS side instead. Always returns false here.
        call.resolve(JSObject().put("running", false))
    }

    private fun hasMicPermission(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED

    private fun hasNotificationPermission(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED
    }
}
