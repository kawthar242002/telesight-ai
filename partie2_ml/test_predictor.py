import sys
sys.path.insert(0, 'api')
try:
    from predictor import TelecomPredictor
    p = TelecomPredictor()
    print("OK - Predictor loaded")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
