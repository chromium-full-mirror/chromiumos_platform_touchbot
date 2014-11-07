from optofidelity.latency import (TapLatencyTest, TouchMoveLatencyTest,
                                  ScrollLatencyTest, ScrollStartLatencyTest)
from optofidelity.system import OptofidelityTestSystem
from optofidelity.test_runner import TestRunner
from optofidelity.test_run import TestRun
from optofidelity.detection import ProcessorDebugger

TestRunner.RegisterTestClass(TapLatencyTest)
TestRunner.RegisterTestClass(TouchMoveLatencyTest)
TestRunner.RegisterTestClass(ScrollLatencyTest)
TestRunner.RegisterTestClass(ScrollStartLatencyTest)
