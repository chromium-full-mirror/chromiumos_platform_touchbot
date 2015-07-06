// Copyright (c) 2015 The Chromium OS Authors. All Rights reserved.
// Use of this source code is governemd by a BSD-style license that can be
// found in the LICENSE file.

/* Python wrapper for accessing the xiQ USB3.0 camera.
 * ===================================================
 * This file contains wrappers that allow access of general functions
 * to control the xiQ camera. To use, run "make" and import xiCam
 * to your python file.
 */

#include <boost/python.hpp>
#include <boost/python/numeric.hpp>
#include <m3api/xiApi.h>
#include <m3api/m3Api.h>
#include <m3api/m3Ext.h>
#include <string>
#include <iostream>
#include <stdint.h>
#include <vector>
#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>

namespace bp = boost::python;
// Maximum buffer size allowed by API
int kMaxBuf = 40*1024*1024;
// Large queue size to avoid frame skipping
int kMaxQ = 500;

struct HandHolder
{
  HandHolder() : triggered_(false), frames_captured_(0) {
    handle_ = INVALID_HANDLE_VALUE;
  }
  // Handle to camera
  HANDLE handle_;
  bool triggered_;
  // Most recent collection of stored images
  std::vector<XI_IMG> image_store_;
  // Number of frames captured so far
  int frames_captured_;
};

int Cameras() {
  DWORD num_devices = 0;
  XI_RETURN stat = xiGetNumberDevices(&num_devices);
  if (stat!=XI_OK) return -1;
  return num_devices;
}

// Initializes the xiCam camera with the sepcified framerate, exposure
// and gain. Returns a handle object to be used with other functions.
HandHolder InitHandle(int fps, int exposure, float gain) {
  HandHolder holder;
  DWORD index = 0;
  char* env = getenv("CAM_INDEX");
  if (env) {
    index = atoi(env);
  }
  DWORD num_devices = 0;
  XI_RETURN stat = XI_OK;
  stat = xiGetNumberDevices(&num_devices);
  if (stat != XI_OK) return holder;
  if (num_devices > 0) {
    stat = xiOpenDevice(index, &(holder.handle_));
    if (stat != XI_OK) return holder;
  }
  // xiQ camera is B&W: user RAW8 or MONO
  xiSetParamInt(holder.handle_, XI_PRM_IMAGE_DATA_FORMAT, XI_RAW8);
  // Set the timing mode to user-controlled frame rate
  xiSetParamInt(holder.handle_, XI_PRM_ACQ_TIMING_MODE, XI_ACQ_TIMING_MODE_FRAME_RATE);
  // Set the frame rate
  xiSetParamInt(holder.handle_, XI_PRM_FRAMERATE, fps);
  // Safe buffer policy: makes copies of XI_IMG structures
  xiSetParamInt(holder.handle_, XI_PRM_BUFFER_POLICY, XI_BP_SAFE);
  // Set exposure
  xiSetParamInt(holder.handle_, XI_PRM_EXPOSURE, exposure);
  // Set Gain
  xiSetParamFloat(holder.handle_, XI_PRM_GAIN, gain);
  // Set queue and buffer sizes
  xiSetParamInt(holder.handle_, XI_PRM_ACQ_BUFFER_SIZE, kMaxBuf);
  xiSetParamInt(holder.handle_, XI_PRM_BUFFERS_QUEUE_SIZE, kMaxQ);
  return holder;
}

// Sets FPS of camera to specified value.
int SetFps(float fps, HandHolder& holder) {
  if(holder.handle_ == INVALID_HANDLE_VALUE) return -1;
  xiSetParamFloat(holder.handle_, XI_PRM_FRAMERATE, fps);
  return 0;
}

// Returns the current FPS reading of the camera.
float Fps(HandHolder& holder) {
  float fps=0;
  xiGetParamFloat(holder.handle_, XI_PRM_FRAMERATE, &fps);
  return fps;
}

// Converts a XI_IMG object to a frame tuple, which consists of
// an ndarray (or numpy array), the frame number, time elapsed
// in milliseconds, and GPI data.
bp::tuple ImgToFrame(XI_IMG &img) {
  bp::list list;
  int width = img.width;
  int height = img.height;
  int size = width * height;
  // Use OpenCV to convert from XI_IMG to numpy array
  cv::Mat frame(cv::Size(width, height), CV_8U, img.bp);
  for(int i = 0; i < frame.rows; ++i)
    for (int j = 0; j < frame.cols; ++j)
      list.append(frame.at<uint8_t>(i,j));
  bp::numeric::array arr(list);
  arr.resize(height,width);
  double mS = (double)img.tsUSec / 1000;
  return bp::make_tuple(arr, img.nframe, mS, img.GPI_level);
}

// Returns a garbage 3X3 frame of zeros. This frame is returned
// by functions that encounter errors accessing real frame data.
bp::tuple GarbageFrame() {
  bp::list list;
  list.append(bp::make_tuple(0,0,0,0,0,0,0,0,0));
  bp::numeric::array arr(list);
  arr.resize(3,3);
  return bp::make_tuple(arr, -1, -1, -1);
}

// Sets the XI_IMG pointer to the most recent image in the buffer.
// REturns 0 on success, -1 on failure.
int GetLastImg(XI_IMG* img, HandHolder& holder) {
  if (holder.triggered_) {
    img->size = sizeof(XI_IMG);
    img->bp = NULL;
    img->bp_size = 0;
    XI_RETURN stat = xiGetImage(holder.handle_, 100, img);
    if (stat == XI_OK) return 0;
  }
  return -1;
}

// Returns the next image in the buffer as a frame tuple.
bp::tuple GetCurrentImg(HandHolder& holder) {
  if (holder.triggered_) {
    XI_IMG img;
    img.size = sizeof(XI_IMG);
    img.bp = NULL;
    img.bp_size = 0;
    XI_RETURN stat = xiGetImage(holder.handle_, 100, &img);
    if (stat != XI_OK) return GarbageFrame();
    return ImgToFrame(img);
  }
  return GarbageFrame();
}

// Triggers the recording to start filling internal image buffers.
// Returns -1 if camera has not been intiialized or fails to respond.
int Trigger(HandHolder& holder) {
  if (holder.handle_ == INVALID_HANDLE_VALUE) return -1;
  if(!holder.triggered_) xiStartAcquisition(holder.handle_);
  holder.triggered_ = true;
  return 0;
}
// Stops camera acquisition and clears the internal buffers.
// Returns 0 on success, -1 on failure.
int StopTrigger(HandHolder& holder) {
  if (holder.handle_ == INVALID_HANDLE_VALUE) return -1;
  if(holder.triggered_) xiStopAcquisition(holder.handle_);
  holder.triggered_ = false;
  return 0;
}

// Closes the camera
void CloseCam(HandHolder& holder) {
  StopTrigger(holder);
  if (holder.handle_ != INVALID_HANDLE_VALUE) xiCloseDevice(holder.handle_);
}
// The FrameSet structure is returned after a call to the python
// wrapped function trigger (xiCam.trigger(500)). The trigger function
// will return a frameset, from which one can access frame data at any index.
struct FrameSet
{
  FrameSet(std::vector<XI_IMG> imgs) : images_(imgs) {};
  bp::tuple getFrame(int frameIdx) {
    if (frameIdx >= images_.size()) return GarbageFrame();
    XI_IMG img = images_[frameIdx];
    return ImgToFrame(img);
  }
  std::vector<XI_IMG> images_;

};


// Triggers the camera, records the specified number of frames
// and returns a frameset for easy access of frame data.
FrameSet TriggerFrames(int frames, HandHolder& holder) {
  holder.image_store_.clear();
  Trigger(holder);
  holder.frames_captured_ = frames;
  for(int i = 0; i < frames; i++) {
    XI_IMG img;
    if (GetLastImg(&img, holder) >= 0) holder.image_store_.push_back(img);
    else holder.frames_captured_--;
  }
  StopTrigger(holder);
  FrameSet set1(holder.image_store_);
  return set1;
}

// Initializes boost functions for visibility within python.

BOOST_PYTHON_MODULE(xiCam) {
  using namespace boost::python;
  numeric::array::set_module_and_type("numpy", "ndarray");
  class_<FrameSet>("FrameSet", init<std::vector<XI_IMG> >())
    .def("getFrame", &FrameSet::getFrame);
  class_<HandHolder>("HandHolder", init<>());
  def("initCam", InitHandle);
  def("trigger", &TriggerFrames);
  def("close",&CloseCam);
  def("setFPS", &SetFps);
  def("fps", &Fps);
  def("start", &Trigger);
  def("stop", &StopTrigger);
  def("curr", &GetCurrentImg);
  def("cameras", &Cameras);
}
