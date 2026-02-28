# Friendly Router - Fine-tuning

Fine-tune Mistral model for intent classification.

## Training Data
- **110 examples** covering:
  - `blitz` - Find services, get quotes, check availability
  - `bounce` - Cancel subscriptions
  - `queue` - Wait on hold for someone
  - `bid` - Negotiate bills
  - `chat` - General conversation

---

## RECOMMENDED: Mistral AI Studio (Use Your $15 Credits)

### Step 1: Get your API key
1. Go to https://console.mistral.ai/api-keys
2. Create a new API key
3. Copy it

### Step 2: Run the fine-tuning script
```bash
cd /Users/deepnandre/Desktop/Friendly/fine-tuning

# Install Mistral SDK
pip install mistralai

# Set your API key
export MISTRAL_API_KEY=your_key_here

# Start fine-tuning
python mistral_finetune.py
```

### Step 3: Wait for training (~30-60 min)
- Script will print job ID and status
- You can close terminal and check at: https://console.mistral.ai/fine-tuning
- Cost: ~$4 minimum + $2/month storage

### Step 4: Use the model
```python
from mistralai import Mistral

client = Mistral(api_key="your_key")
response = client.chat.complete(
    model="ft:open-mistral-7b:xxxxx",  # Your fine-tuned model ID
    messages=[{"role": "user", "content": "find me a plumber"}]
)
```

---

## Alternative: HuggingFace (Use Your $20 Credits)

If you prefer HuggingFace:
1. Go to https://huggingface.co/autotrain
2. Upload `training_data.jsonl`
3. Select base model: `mistralai/Ministral-8B-Instruct-2410`

---

## Expected Output

After fine-tuning, the model outputs JSON:

```json
{"agent": "blitz", "params": {"service": "plumber", "timeframe": "tomorrow"}}
```

---

## Fallback (If Fine-tuning Fails)

Use Mistral Large with this system prompt:

```
You are a router for Friendly. Classify user intent and output JSON only:
{"agent": "blitz|bounce|queue|bid|chat", "params": {...}}

Agents:
- blitz: Find services, get quotes, check availability
- bounce: Cancel subscriptions
- queue: Wait on hold for user
- bid: Negotiate bills lower
- chat: General conversation
```
