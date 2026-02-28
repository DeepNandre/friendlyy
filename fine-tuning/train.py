"""
Fine-tune Ministral-8B for intent classification (Friendly Router)
Run this on HuggingFace or locally with GPU

Usage:
  pip install -r requirements.txt
  huggingface-cli login
  python train.py
"""

import os
import json
from datasets import load_dataset, Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, TaskType
import torch

# Configuration
MODEL_NAME = "mistralai/Ministral-8B-Instruct-2410"  # or Ministral-3B if you want faster
OUTPUT_DIR = "./friendly-router"
DATASET_PATH = "./training_data.jsonl"

# LoRA config for efficient fine-tuning
LORA_CONFIG = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,  # rank
    lora_alpha=32,
    lora_dropout=0.1,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
)

def format_conversation(example):
    """Format the conversation for Mistral instruction format"""
    messages = example["messages"]

    # Mistral instruction format
    text = ""
    for msg in messages:
        if msg["role"] == "user":
            text += f"<s>[INST] {msg['content']} [/INST]"
        elif msg["role"] == "assistant":
            text += f" {msg['content']}</s>"

    return {"text": text}


def main():
    print("Loading dataset...")

    # Load from JSONL
    with open(DATASET_PATH, "r") as f:
        data = [json.loads(line) for line in f]

    dataset = Dataset.from_list(data)
    dataset = dataset.map(format_conversation)

    print(f"Loaded {len(dataset)} examples")
    print(f"Sample: {dataset[0]['text'][:200]}...")

    # Split into train/eval
    dataset = dataset.train_test_split(test_size=0.1)

    print("Loading model and tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
        device_map="auto",
    )

    # Apply LoRA
    print("Applying LoRA...")
    model = get_peft_model(model, LORA_CONFIG)
    model.print_trainable_parameters()

    # Tokenize
    def tokenize(example):
        return tokenizer(
            example["text"],
            truncation=True,
            max_length=512,
            padding="max_length",
        )

    tokenized_train = dataset["train"].map(tokenize, batched=True)
    tokenized_eval = dataset["test"].map(tokenize, batched=True)

    # Training arguments
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_steps=50,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_steps=100,
        fp16=True,
        push_to_hub=True,
        hub_model_id="friendly-router",
    )

    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_eval,
        data_collator=data_collator,
    )

    print("Starting training...")
    trainer.train()

    print("Saving model...")
    trainer.save_model()
    trainer.push_to_hub()

    print(f"Done! Model saved to {OUTPUT_DIR} and pushed to HuggingFace Hub")


if __name__ == "__main__":
    main()
