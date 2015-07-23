package org.chromium.touchlatency;

import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBarActivity;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;


public class MainMenuActivity extends ActionBarActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main_menu);
    }


    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        // Inflate the menu; this adds items to the action bar if it is present.
        getMenuInflater().inflate(R.menu.menu_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        // Handle action bar item clicks here. The action bar will
        // automatically handle clicks on the Home/Up button, so long
        // as you specify a parent activity in AndroidManifest.xml.
        int id = item.getItemId();

        //noinspection SimplifiableIfStatement
        if (id == R.id.action_settings) {
            return true;
        }

        return super.onOptionsItemSelected(item);
    }

    public void OpenFlashPage(View view) {
        Intent myIntent = new Intent(this, FlashActivity.class);
        MainMenuActivity.this.startActivity(myIntent);
    }

    public void OpenTapPage(View view) {
        Intent myIntent = new Intent(this, TapActivity.class);
        MainMenuActivity.this.startActivity(myIntent);
    }

    public void OpenScrollPage(View view) {
        Intent myIntent = new Intent(this, ScrollActivity.class);
        MainMenuActivity.this.startActivity(myIntent);
    }
}
