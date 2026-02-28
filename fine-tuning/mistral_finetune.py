"""
Fine-tune Mistral model for Friendly Router
Using Mistral AI Studio API

Prerequisites:
    pip install mistralai
    export MISTRAL_API_KEY=your_key_here

Usage:
    python mistral_finetune.py
"""

import os
import time
from mistralai import Mistral

# Get API key
api_key = os.environ.get("MISTRAL_API_KEY")
if not api_key:
    print("ERROR: Set MISTRAL_API_KEY environment variable")
    print("  export MISTRAL_API_KEY=your_key_here")
    exit(1)

client = Mistral(api_key=api_key)

# Config
TRAINING_FILE = "training_data.jsonl"
BASE_MODEL = "ministral-3b-latest"  # Small, fast, perfect for routing
TRAINING_STEPS = 100  # Adjust based on dataset size
LEARNING_RATE = 0.0001


def main():
    print("=" * 50)
    print("Friendly Router - Mistral Fine-tuning")
    print("=" * 50)

    # Step 1: Upload training file
    print("\n[1/4] Uploading training data...")
    with open(TRAINING_FILE, "rb") as f:
        training_file = client.files.upload(
            file={
                "file_name": TRAINING_FILE,
                "content": f,
            }
        )
    print(f"  Uploaded: {training_file.id}")

    # Step 2: Create fine-tuning job
    print(f"\n[2/4] Creating fine-tuning job (base: {BASE_MODEL})...")
    job = client.fine_tuning.jobs.create(
        model=BASE_MODEL,
        training_files=[{"file_id": training_file.id, "weight": 1}],
        hyperparameters={
            "training_steps": TRAINING_STEPS,
            "learning_rate": LEARNING_RATE,
        },
        auto_start=True,
    )
    print(f"  Job ID: {job.id}")
    print(f"  Status: {job.status}")

    # Step 3: Wait for completion
    print("\n[3/4] Training in progress...")
    print("  (This may take 30-60 minutes. You can close this and check later.)")
    print(f"  Check status: https://console.mistral.ai/fine-tuning/{job.id}")

    while True:
        retrieved_job = client.fine_tuning.jobs.get(job_id=job.id)
        status = retrieved_job.status

        if status == "SUCCESS":
            print(f"\n  Training complete!")
            break
        elif status in ["FAILED", "CANCELLED"]:
            print(f"\n  Training {status}!")
            print(f"  Check console for details: https://console.mistral.ai/fine-tuning/{job.id}")
            exit(1)
        else:
            print(f"  Status: {status}...", end="\r")
            time.sleep(30)

    # Step 4: Get fine-tuned model ID
    fine_tuned_model = retrieved_job.fine_tuned_model
    print(f"\n[4/4] Fine-tuned model ready!")
    print(f"  Model ID: {fine_tuned_model}")

    # Test it
    print("\n" + "=" * 50)
    print("Testing fine-tuned model...")
    print("=" * 50)

    test_messages = [
        "find me a plumber who can come tomorrow",
        "cancel my Netflix subscription",
        "call HMRC and wait on hold for me",
        "negotiate my Sky bill down",
        "hello, what can you do?",
    ]

    for msg in test_messages:
        response = client.chat.complete(
            model=fine_tuned_model,
            messages=[{"role": "user", "content": msg}],
        )
        result = response.choices[0].message.content
        print(f"\nInput: {msg}")
        print(f"Output: {result}")

    # Save model ID for later use
    with open("fine_tuned_model_id.txt", "w") as f:
        f.write(fine_tuned_model)

    print("\n" + "=" * 50)
    print("SUCCESS! Model ID saved to fine_tuned_model_id.txt")
    print(f"Use this in your code: model=\"{fine_tuned_model}\"")
    print("=" * 50)


if __name__ == "__main__":
    main()
