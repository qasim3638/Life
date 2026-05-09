package com.qasim.lifeblueprint;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private static final int MIC_PERMISSION_REQ = 4242;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Register the HandsFree plugin (Phase B) before super.onCreate
        // so the plugin is available to the WebView.
        registerPlugin(HandsFreePlugin.class);
        super.onCreate(savedInstanceState);

        // Runtime permission request — Android requires this even when
        // RECORD_AUDIO is declared in the manifest. Without it, JavaScript
        // getUserMedia() inside the WebView fails with "permission denied".
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            String[] needed = {
                Manifest.permission.RECORD_AUDIO,
                Manifest.permission.POST_NOTIFICATIONS,
            };
            boolean shouldRequest = false;
            for (String p : needed) {
                if (ContextCompat.checkSelfPermission(this, p) != PackageManager.PERMISSION_GRANTED) {
                    shouldRequest = true;
                    break;
                }
            }
            if (shouldRequest) {
                ActivityCompat.requestPermissions(this, needed, MIC_PERMISSION_REQ);
            }
        }
    }
}
