import numpy as np
import json

times = [0.1, 0.2, 0.3]
avg_time = np.mean(times)
passed = avg_time <= 2.0

print(f"Type of avg_time: {type(avg_time)}")
print(f"Type of passed: {type(passed)}")

try:
    json.dumps({"passed": passed})
    print("JSON dump successful")
except TypeError as e:
    print(f"JSON dump failed: {e}")
