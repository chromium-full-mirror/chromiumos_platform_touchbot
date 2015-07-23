// Copyright 2015 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import UIKit

class ScrollViewController: UIViewController, UIScrollViewDelegate {
    @IBOutlet var scrollView: UIScrollView!
    @IBOutlet var topView: UIView!
    @IBOutlet var bottomView: UIView!
    
    override func viewDidLoad() {
        super.viewDidLoad()
        scrollView.contentSize = CGSize(width: 64.0, height: 2048.0)
        var tapRecognizer = UITapGestureRecognizer(target: self, action: Selector("onTap:"))
        view.addGestureRecognizer(tapRecognizer)
    }
    
    func onTap(sender: UITapGestureRecognizer) {
        if sender.state == .Ended {
            // Scroll black-white edge to finger location
            var y = sender.locationInView(view).y
            var rel_y = y - scrollView.contentOffset.y
            var target_scroll = 1024 - rel_y
            scrollView.setContentOffset(CGPoint(x:0, y:target_scroll), animated: false)
            
            // flip color depending on where the finger tapped.
            if rel_y < view.frame.size.height / 2 {
                topView.backgroundColor = UIColor.blackColor()
                bottomView.backgroundColor = UIColor.whiteColor()
            } else {
                topView.backgroundColor = UIColor.whiteColor()
                bottomView.backgroundColor = UIColor.blackColor()
            }
        }
    }
}

