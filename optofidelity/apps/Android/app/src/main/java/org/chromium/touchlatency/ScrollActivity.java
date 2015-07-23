package org.chromium.touchlatency;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.MotionEvent;
import android.view.View;


public class ScrollActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_scroll);

        View scrollView = findViewById(R.id.scrollView);
        scrollView.setOnTouchListener(new View.OnTouchListener() {
            @Override
            public boolean onTouch(View scrollView, MotionEvent event) {
                View topBar = findViewById(R.id.topBar);
                View bottomBar = findViewById(R.id.bottomBar);
                switch(event.getAction()){
                    case MotionEvent.ACTION_DOWN:
                        float y = event.getY();
                        float center = scrollView.getHeight() * 0.5f;
                        if (y > center) {
                            topBar.setBackgroundColor(Color.WHITE);
                            bottomBar.setBackgroundColor(Color.BLACK);
                        } else {
                            topBar.setBackgroundColor(Color.BLACK);
                            bottomBar.setBackgroundColor(Color.WHITE);
                        }
                        scrollView.scrollTo(0, 2048 - (int)y);
                        break;
                }
                return false;
            }
        });
    }

}
