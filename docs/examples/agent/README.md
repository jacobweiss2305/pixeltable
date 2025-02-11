# Steps to reproduce

The steps below will provide you with the time taken on v.0.3.0 compared to v0.3.2

1. Create venv and activate
```
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies
```
pip install -r requirements.txt
```

3. Run the script on v.0.3.0
```
python example.py
```
This takes about 14 seconds to run.

4. Note the Total execution time in the output

5. Install latest pixeltable
```
pip install -U pixeltable
```

6. Run the script again
```
python example.py
```

This takes about 27 seconds to run.

