// Copyright 2015 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import UIKit

class FlashViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor.blackColor()
        var timer = NSTimer.scheduledTimerWithTimeInterval(0.1, target: self, selector: Selector("flash"), userInfo: nil, repeats: true)
    }
    
    func flash() {
        if (view.backgroundColor == UIColor.blackColor()) {
            view.backgroundColor = UIColor.whiteColor();
        } else {
            view.backgroundColor = UIColor.blackColor();
        }
    }
}

