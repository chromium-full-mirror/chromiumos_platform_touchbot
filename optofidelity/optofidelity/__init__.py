from optofidelity.latency import (TapLatencyTest, TouchMoveLatencyTest,
                                  ScrollLatencyTest, ScrollStartLatencyTest,
                                  MockLatencyTest)
from optofidelity.system import OptofidelityTestSystem, MockTestSystem
from optofidelity.test_runner import TestRunner
from optofidelity.test_run import TestRun, MeasurementList
from optofidelity.detection import ProcessorDebugger
from optofidelity.report import Reporter
TestRunner.RegisterTestClass(TapLatencyTest)
TestRunner.RegisterTestClass(TouchMoveLatencyTest)
TestRunner.RegisterTestClass(ScrollLatencyTest)
TestRunner.RegisterTestClass(ScrollStartLatencyTest)
