package com.qasim.lifeblueprint;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Register the HandsFree plugin (Phase B) before super.onCreate
        // so the plugin is available to the WebView.
        registerPlugin(HandsFreePlugin.class);
        super.onCreate(savedInstanceState);
    }
}
