package com.qasim.lifeblueprint

import ai.picovoice.android.voiceprocessor.VoiceProcessor
import ai.picovoice.android.voiceprocessor.VoiceProcessorFrameListener
import ai.picovoice.eagle.Eagle
import ai.picovoice.porcupine.Porcupine
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Base64
import android.util.Log
import androidx.core.app.NotificationCompat

/**
 * HandsFreeService — Phase B always-on listener.
 *
 * Stays alive as a foreground service while the app is open or backgrounded.
 * Runs Picovoice Porcupine ("Hi Yaar") + optionally Eagle (voiceprint) on
 * the same audio stream from VoiceProcessor.
 *
 * On detection it broadcasts an intent that HandsFreePlugin forwards to the
 * WebView via Capacitor, which opens VoiceMicButton for chat.
 *
 * IMPORTANT: this service requires:
 *   - RECORD_AUDIO + FOREGROUND_SERVICE_MICROPHONE permissions (manifest)
 *   - User-granted runtime mic permission (handled by HandsFreePlugin)
 *   - Picovoice AccessKey + model files copied into a known location
 */
class HandsFreeService : Service() {

    private val TAG = "HandsFreeService"
    private val CHANNEL_ID = "life_blueprint_yaar_listening"
    private val NOTIFICATION_ID = 4242

    private var porcupine: Porcupine? = null
    private var eagle: Eagle? = null
    private var voiceProcessor: VoiceProcessor? = null
    private var isRunning = false

    private var verifyingFrames: MutableList<ShortArray>? = null
    private var voiceprintEnabled = false
    private var voiceprintThreshold = 0.6f

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val accessKey = intent?.getStringExtra("accessKey") ?: ""
        val keywordPath = intent?.getStringExtra("keywordPath") ?: ""
        val modelPath = intent?.getStringExtra("porcupineModelPath") ?: ""
        val eagleModelPath = intent?.getStringExtra("eagleModelPath")
        val profileBase64 = intent?.getStringExtra("profileBase64")
        voiceprintThreshold = intent?.getFloatExtra("threshold", 0.6f) ?: 0.6f

        if (accessKey.isBlank() || keywordPath.isBlank() || modelPath.isBlank()) {
            Log.e(TAG, "Missing accessKey/keywordPath/modelPath")
            stopSelf()
            return START_NOT_STICKY
        }

        startForegroundCompat()

        try {
            porcupine = Porcupine.Builder()
                .setAccessKey(accessKey)
                .setKeywordPath(keywordPath)
                .setModelPath(modelPath)
                .setSensitivity(0.6f)
                .build(applicationContext)

            if (!eagleModelPath.isNullOrBlank() && !profileBase64.isNullOrBlank()) {
                try {
                    val profileBytes = Base64.decode(profileBase64, Base64.DEFAULT)
                    val profile = ai.picovoice.eagle.EagleProfile(profileBytes)
                    eagle = Eagle.Builder()
                        .setAccessKey(accessKey)
                        .setModelPath(eagleModelPath)
                        .setSpeakerProfiles(arrayOf(profile))
                        .build(applicationContext)
                    voiceprintEnabled = true
                } catch (e: Exception) {
                    Log.w(TAG, "Eagle init failed, continuing without voiceprint: ${e.message}")
                }
            }

            voiceProcessor = VoiceProcessor.getInstance()
            val listener = VoiceProcessorFrameListener { frame ->
                onAudioFrame(frame)
            }
            voiceProcessor?.addFrameListener(listener)
            voiceProcessor?.start(porcupine!!.frameLength, porcupine!!.sampleRate)
            isRunning = true
            Log.i(TAG, "HandsFreeService started (voiceprint=$voiceprintEnabled)")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to init Porcupine: ${e.message}", e)
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    private fun onAudioFrame(frame: ShortArray) {
        if (!isRunning) return
        try {
            // If we're collecting frames for voiceprint verification, do that
            if (verifyingFrames != null) {
                verifyingFrames!!.add(frame.copyOf())
                if (verifyingFrames!!.size >= 50) { // ~1.6s
                    val frames = verifyingFrames!!
                    verifyingFrames = null
                    runVoiceprintCheck(frames)
                }
                return
            }

            val keywordIndex = porcupine?.process(frame) ?: -1
            if (keywordIndex >= 0) {
                Log.i(TAG, "'Hi Yaar' detected")
                if (voiceprintEnabled && eagle != null) {
                    // Buffer ~1.6s of audio for voiceprint check
                    verifyingFrames = mutableListOf()
                } else {
                    fireWake()
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Frame error: ${e.message}")
        }
    }

    private fun runVoiceprintCheck(frames: List<ShortArray>) {
        try {
            val scores = mutableListOf<Float>()
            for (f in frames) {
                val s = eagle!!.process(f)
                if (s.isNotEmpty()) scores.add(s[0])
            }
            val avg = if (scores.isEmpty()) 0f else scores.sum() / scores.size
            if (avg >= voiceprintThreshold) {
                Log.i(TAG, "Voiceprint match $avg")
                fireWake()
            } else {
                Log.i(TAG, "Voiceprint reject $avg")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Voiceprint error: ${e.message}")
        }
    }

    private fun fireWake() {
        sendBroadcast(Intent(ACTION_WAKE).setPackage(packageName))
    }

    override fun onDestroy() {
        isRunning = false
        try { voiceProcessor?.stop() } catch (_: Exception) {}
        try { porcupine?.delete() } catch (_: Exception) {}
        try { eagle?.delete() } catch (_: Exception) {}
        super.onDestroy()
        Log.i(TAG, "HandsFreeService destroyed")
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = getSystemService(NotificationManager::class.java)
            val ch = NotificationChannel(
                CHANNEL_ID,
                "Yaar listening",
                NotificationManager.IMPORTANCE_LOW,
            )
            ch.description = "Yaar is listening for 'Hi Yaar'"
            mgr.createNotificationChannel(ch)
        }
    }

    private fun startForegroundCompat() {
        val launchIntent = packageManager.getLaunchIntentForPackage(packageName)
        val pi = PendingIntent.getActivity(
            this, 0, launchIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notif: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Yaar is listening")
            .setContentText("Say \"Hi Yaar\" anytime")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIFICATION_ID, notif)
        }
    }

    companion object {
        const val ACTION_WAKE = "com.qasim.lifeblueprint.HANDSFREE_WAKE"
    }
}
