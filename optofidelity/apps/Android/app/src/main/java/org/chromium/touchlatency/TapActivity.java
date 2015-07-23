package org.chromium.touchlatency;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.MotionEvent;
import android.view.View;


public class TapActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_tap);

        View main_layout = findViewById(R.id.main_layout);
        main_layout.setOnTouchListener(new View.OnTouchListener() {
            @Override
            public boolean onTouch(View v, MotionEvent event) {
                switch(event.getAction()){

                    case MotionEvent.ACTION_DOWN:
                        v.setBackgroundColor(Color.BLACK);
                        break;
                    case MotionEvent.ACTION_UP:
                        v.setBackgroundColor(Color.WHITE);
                        break;
                }
                return true;
            }
        });
    }
}
