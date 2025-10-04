import os
import glob
import webbrowser
from bs4 import BeautifulSoup
import ttkbootstrap as tb
from ttkbootstrap.dialogs import Messagebox

FOOOCUS_LOGS = "Fooocus/outputs"
FOOOCUS_CHECKPOINTS = "Fooocus/models/checkpoints"
FOOOCUS_LORAS = "Fooocus/models/loras"
OUTPUT_FILE = "search_results.html"


def get_checkpoints():
    return [f for f in os.listdir(FOOOCUS_CHECKPOINTS) if f.lower().endswith((".safetensors", ".ckpt"))] if os.path.exists(FOOOCUS_CHECKPOINTS) else []


def get_loras():
    return [f for f in os.listdir(FOOOCUS_LORAS) if f.lower().endswith((".safetensors", ".pt"))] if os.path.exists(FOOOCUS_LORAS) else []


def split_full_raw_prompt(raw_prompt: str):
    """Splits full raw prompt into positive and negative parts."""
    lower_text = raw_prompt.lower()
    idx_negative = lower_text.find("negative")
    if idx_negative != -1:
        pos = raw_prompt[:idx_negative].strip()
        neg = raw_prompt[idx_negative:].strip()
    else:
        pos = raw_prompt.strip()
        neg = ""
    return pos, neg


def search_logs(prompt_keyword, checkpoint, lora):
    results = []
    log_files = glob.glob(os.path.join(FOOOCUS_LOGS, "*", "log.html"))
    current_checkpoints = get_checkpoints()
    current_loras = get_loras()

    for log_file in log_files:
        date = os.path.basename(os.path.dirname(log_file))
        folder_path = os.path.dirname(log_file)
        with open(log_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        entries = soup.find_all("div", class_="image-container")
        for entry in entries:
            entry_text = entry.get_text(" ", strip=True).lower()

            if prompt_keyword and prompt_keyword.lower() not in entry_text:
                continue

            if checkpoint:
                if checkpoint.lower() == "missing only":
                    missing_cp = True
                    for cp in current_checkpoints:
                        if cp.lower() in entry_text:
                            missing_cp = False
                            break
                    if not missing_cp:
                        continue
                elif checkpoint.lower() not in entry_text:
                    continue

            if lora:
                if lora.lower() == "missing only":
                    missing_lora = True
                    for lr in current_loras:
                        if lr.lower() in entry_text:
                            missing_lora = False
                            break
                    if not missing_lora:
                        continue
                elif lora.lower() not in entry_text:
                    continue

            image_tag = entry.find("img")
            img_src = image_tag['src'] if image_tag else ""
            img_name = os.path.basename(img_src)

            metadata_table = entry.find("table", class_="metadata")
            params = {}
            lora_count = 0
            if metadata_table:
                for row in metadata_table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) == 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key.lower().startswith("lora"):
                            lora_count += 1
                            params[f"LoRA {lora_count}"] = value
                        else:
                            params[key] = value

            results.append({
                "date": date,
                "folder": folder_path,
                "img_src": os.path.join(folder_path, img_src),
                "img_name": img_name,
                "params": params
            })
    return results


def run_search():
    prompt_keyword = prompt_var.get().strip()
    checkpoint = checkpoint_var.get().strip()
    lora = lora_var.get().strip()
    results = search_logs(prompt_keyword, checkpoint, lora)
    results.sort(key=lambda x: x["date"], reverse=True)

    if not results:
        Messagebox.show_info("No results found.")
        return

    current_checkpoints = get_checkpoints()
    current_loras = get_loras()

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Fooocus Search Results</title>
<style>
body {{ background-color: #121212; color: #E0E0E0; font-family: sans-serif; margin: 10px; }}
a {{ color: #BB86FC; text-decoration: none; }}
.gallery {{ display: flex; flex-direction: column; gap: 20px; }}
.entry {{ display: flex; gap: 20px; border-bottom: 1px solid #444; padding: 10px; flex-wrap: wrap; }}
.left {{ flex: 0 0 40%; max-width: 40%; }}
.left img {{ width: 100%; height: auto; display: block; }}
.left .filename {{ font-weight: bold; margin-top: 5px; }}
.left .folder {{ font-size: 0.9em; color: #CCC; }}
.right {{ flex: 0 0 58%; max-width: 58%; }}
.right table {{ border-collapse: collapse; width: 100%; }}
.right th, .right td {{ border: 1px solid #4d4d4d; padding: 4px; }}
.right th {{ background-color: #222; text-align: left; width: 30%; }}
.collapsible {{ background-color: #444; color: white; cursor: pointer; padding: 5px; border: none; text-align: left; width: 100%; }}
.content {{ display: none; padding: 5px; background-color: #333; white-space: pre-wrap; }}
.present {{ background-color: green; color: white; }}
.missing {{ background-color: yellow; color: black; }}
</style>
</head>
<body>
<h1>Search Results ({len(results)} entries)</h1>
<div class="gallery">
<script>
document.addEventListener("DOMContentLoaded", function(){{
    var coll = document.getElementsByClassName("collapsible");
    for (var i = 0; i < coll.length; i++) {{
        coll[i].addEventListener("click", function() {{
            this.classList.toggle("active");
            var content = this.nextElementSibling;
            content.style.display = (content.style.display === "block") ? "none" : "block";
        }});
    }}
}});
</script>
"""

    for r in results:
        html_content += f"""
<div class="entry">
    <div class="left">
        <img src="{r['img_src']}" loading="lazy"/>
        <div class="filename">{r['img_name']}</div>
        <div class="folder"><a href="file:///{r['folder']}" target="_blank">{r['folder']}</a></div>
    </div>
    <div class="right">
        <table class="metadata">
"""

        prompt_keys = ["prompt", "negative prompt", "fooocus v2 expansion", "full raw prompt"]

        for key, value in r["params"].items():
            cell_class = ""
            if key.lower() in ["checkpoint", "base model"]:
                cell_class = "present" if any(cp.lower() in value.lower() for cp in current_checkpoints) else "missing"
            elif key.lower().startswith("lora"):
                cell_class = "present" if any(lr.lower() in value.lower() for lr in current_loras) else "missing"

            if key.lower() == "full raw prompt":
                pos_prompt, neg_prompt = split_full_raw_prompt(value)
                html_content += f"""
<tr><th>{key}</th>
<td>
<button class="collapsible">Show Full Raw Prompt</button>
<div class="content">
    <button class="collapsible">Raw Positive Prompt</button>
    <div class="content">{pos_prompt}</div>
    <button class="collapsible">Raw Negative Prompt</button>
    <div class="content">{neg_prompt}</div>
</div>
</td></tr>
"""
            elif key.lower() in prompt_keys and key.lower() != "full raw prompt":
                html_content += f"""
<tr><th>{key}</th>
<td>
<button class="collapsible">Show {key}</button>
<div class="content">{value}</div>
</td></tr>
"""
            elif key.lower() not in ["negative prompt"]:
                html_content += f"<tr><th>{key}</th><td class='{cell_class}'>{value}</td></tr>"

        html_content += """
        </table>
    </div>
</div>
"""

    html_content += "</div></body></html>"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    webbrowser.open("file://" + os.path.abspath(OUTPUT_FILE))
    app.after(500, app.destroy)


# GUI with ttkbootstrap
app = tb.Window(themename="darkly")
app.title("Fooocus Prompt Search")

tb.Label(app, text="Prompt contains:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
prompt_var = tb.StringVar()
tb.Entry(app, textvariable=prompt_var, width=40).grid(row=0, column=1, padx=5, pady=5)

tb.Label(app, text="Checkpoint:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
checkpoint_var = tb.StringVar()
checkpoint_values = get_checkpoints()
checkpoint_values.append("missing only")
checkpoint_dropdown = tb.Combobox(app, textvariable=checkpoint_var, values=checkpoint_values, width=37, state="readonly")
checkpoint_dropdown.grid(row=1, column=1, padx=5, pady=5)

tb.Label(app, text="LoRA:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
lora_var = tb.StringVar()
lora_values = get_loras()
lora_values.append("missing only")
lora_dropdown = tb.Combobox(app, textvariable=lora_var, values=lora_values, width=37, state="readonly")
lora_dropdown.grid(row=2, column=1, padx=5, pady=5)

tb.Button(app, text="Search", command=run_search, bootstyle=tb.SUCCESS).grid(row=3, column=0, columnspan=2, pady=15)

app.mainloop()
