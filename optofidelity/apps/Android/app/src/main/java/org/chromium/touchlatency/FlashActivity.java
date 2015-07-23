package org.chromium.touchlatency;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.view.View;


public class FlashActivity extends Activity {
    Handler timerHandler = new Handler();
    View main_layout;
    int background_color = Color.WHITE;

    Runnable timerRunnable = new Runnable() {
        @Override
        public void run() {
            if (background_color == Color.WHITE) {
                background_color = Color.BLACK;
            } else {
                background_color = Color.WHITE;
            }
            main_layout.setBackgroundColor(background_color);
            timerHandler.postDelayed(this, 100);
        }
    };
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_flash);
        main_layout = findViewById(R.id.main_layout);
        timerHandler.postDelayed(timerRunnable, 100);
    }
}
