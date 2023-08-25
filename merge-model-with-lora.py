import os

import torch
import transformers
from peft import PeftModel
from transformers import LlamaForCausalLM, LlamaTokenizer, LlamaConfig  # noqa: F402
import argparse
import shutil

# Create the parser
parser = argparse.ArgumentParser(description="Merge model with LoRA/QLoRA/Peft/Adapter")

# Add the arguments
parser.add_argument("model", type=str, help="Base Model")
parser.add_argument("lora", type=str, help="LoRA/QLoRA/Peft/Adapter Model")

args = parser.parse_args()

base_model_name = args.model
lora = args.lora

tokenizer = LlamaTokenizer.from_pretrained(base_model_name)

base_model = LlamaForCausalLM.from_pretrained(
    base_model_name,
    load_in_8bit=False,
    torch_dtype=torch.float16,
    device_map={"": "cpu"},
)

first_weight = base_model.model.layers[0].self_attn.q_proj.weight
first_weight_old = first_weight.clone()

lora_model = PeftModel.from_pretrained(
    base_model,
    lora,
    device_map={"": "cpu"},
    torch_dtype=torch.float16,
)

lora_weight = lora_model.base_model.model.model.layers[
    0
].self_attn.q_proj.weight

assert torch.allclose(first_weight_old, first_weight)

# merge weights - new merging method from peft
print("Merging . . .")
lora_model = lora_model.merge_and_unload()

lora_model.train(False)

# did we do anything?
assert not torch.allclose(first_weight_old, first_weight)

lora_model_sd = lora_model.state_dict()
deloreanized_sd = {
    k.replace("base_model.model.", ""): v
    for k, v in lora_model_sd.items()
    if "lora" not in k
}

print("Merge complete! Saving to disk . . .")
LlamaForCausalLM.save_pretrained(
    base_model, "./merged_model", state_dict=deloreanized_sd, max_shard_size="10GB"
)

print("""Note: You only need those files(Ignore if one of them doesn't exist.):
            pytorch_model.bin
            every pytorch_model-<number>-<number>.bin
            pytorch_model.bin.index.json
        Copy/re-use the rest of them from base model.
        """)
