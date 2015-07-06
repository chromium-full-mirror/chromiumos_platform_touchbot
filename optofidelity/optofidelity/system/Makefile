# Copyright (c) 2015 The Chromium OS Authors. All Rights reserved.
# Use of this source code is governemd by a BSD-style license that can be
# found in the LICENSE file.
PYTHON_VERSION = 2.7
PYTHON_INCLUDE = /usr/include/python$(PYTHON_VERSION)

BOOST_INC = /usr/include
BOOST_LIB = /usr/lib

TARGET = xiCam

$(TARGET).so: $(TARGET).o
	g++ -shared -Wl,--no-undefined $(TARGET).o `pkg-config opencv --cflags --libs` -L$(BOOST_LIB) -lboost_python -L/usr/lib -L/usr/lib/python$(PYTHON_VERSION)/config -lpython$(PYTHON_VERSION) -lm3api -o $(TARGET).so

$(TARGET).o: $(TARGET).cpp
	g++ -I$(PYTHON_INCLUDE) -I$(BOOST_INC) -fPIC -c $(TARGET).cpp

clean:
	rm -rf $(TARGET).o $(TARGET).so

