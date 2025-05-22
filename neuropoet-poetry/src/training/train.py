import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model

# Load dataset
dataset = load_dataset("json", data_files="../../data/processed_dataset.jsonl")

# Initialize tokenizer
tokenizer = AutoTokenizer.from_pretrained("ai-forever/rugpt3small_based_on_gpt2")
tokenizer.pad_token = tokenizer.eos_token

# Tokenize function
def tokenize_function(examples):
    tokenized = tokenizer(
        examples["text"],
        truncation=True,
        padding="max_length",
        max_length=192
    )
    tokenized["labels"] = tokenized["input_ids"].copy()
    return tokenized

tokenized_datasets = dataset.map(tokenize_function, batched=True)

# Efficient quantization setup
quantization_config = BitsAndBytesConfig(
    load_in_8bit=True,
    llm_int8_threshold=6.0
)

# Download (if necessary) and load pre-trained model with quantization
model = AutoModelForCausalLM.from_pretrained(
    "ai-forever/rugpt3small_based_on_gpt2",
    quantization_config=quantization_config,
    device_map="auto"
)

# LoRA configuration for efficient fine-tuning
lora_config = LoraConfig(
    r=8,
    lora_alpha=32,
    target_modules=["c_attn", "c_proj"],
    lora_dropout=0.1,
    bias="none",
    task_type="CAUSAL_LM"
)

model = get_peft_model(model, lora_config)

# Define training arguments
training_args = TrainingArguments(
    output_dir="../../models/rugpt3_finetuned",
    per_device_train_batch_size=8,
    gradient_accumulation_steps=6,
    num_train_epochs=8,
    save_steps=1000,
    learning_rate=2e-4,
    logging_steps=500,
    fp16=True,
    logging_dir="../../models/rugpt3_finetuned/logs",
)

# Setup trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_datasets["train"],
    tokenizer=tokenizer
)

# Train and save the fine-tuned model
trainer.train()
trainer.save_model("../../models/rugpt3_finetuned")

print("Fine-tuning complete. Model saved.")
