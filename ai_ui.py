"""Tk views for the AI garage. Workers never access Tk widgets."""
import copy
import json
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

from ai_garage import (AIStore, answer_question, generate_portrait, portrait_prompt,
                       prepare_workflow, request_json, endpoint)


class AIGarageWindow(tk.Toplevel):
    def __init__(self, parent, car, directory):
        super().__init__(parent)
        self.title('AI Garage | ' + car['name'])
        self.transient(parent)
        self.geometry('1000x760')
        self.minsize(760, 600)
        self.car = copy.deepcopy(car)
        self.store = AIStore(directory)
        self.history = []
        self.results = queue.Queue()
        self.busy = False
        self.stopped = threading.Event()
        self.protocol('WM_DELETE_WINDOW', self.close)
        ttk.Label(self, text='AI Garage · ' + car['name'], font=('Helvetica', 18, 'bold')).pack(anchor='w', padx=18, pady=12)
        ttk.Label(self, text='Manuals and portraits are saved locally. Chat uses the configured Ollama server.').pack(anchor='w', padx=18)
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', expand=True, padx=18, pady=12)
        for label, builder in [('Car assistant', self.build_chat), ('Garage portrait', self.build_portrait), ('AI settings', self.build_settings)]:
            frame = ttk.Frame(self.tabs, padding=12)
            self.tabs.add(frame, text=label)
            builder(frame)
        self.status = tk.StringVar(value='Ready · Select a manual that matches this car’s year, engine, and trim.')
        ttk.Label(self, textvariable=self.status, wraplength=920, padding=12).pack(fill='x')
        self.poll_id = self.after(100, self.poll)

    def close(self):
        self.stopped.set()
        self.after_cancel(self.poll_id)
        self.destroy()

    def run_job(self, label, work, done):
        if self.busy:
            messagebox.showinfo('AI Garage', 'Wait for the current task to finish. Closing this window stops waiting.', parent=self)
            return False
        self.busy = True
        self.status.set(label)
        def worker():
            try:
                self.results.put((done, work(), None))
            except Exception as error:
                self.results.put((done, None, str(error)))
        threading.Thread(target=worker, daemon=True).start()
        return True

    def poll(self):
        try:
            done, result, error = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            if error:
                self.status.set('Task failed. Your saved maintenance data was not changed.')
                messagebox.showerror('AI Garage', error, parent=self)
            else:
                self.status.set('Ready')
                done(result)
        self.poll_id = self.after(100, self.poll)

    def build_chat(self, frame):
        tools = ttk.Frame(frame)
        tools.pack(fill='x')
        ttk.Button(tools, text='Import manual', command=self.import_manual).pack(side='left')
        ttk.Button(tools, text='Remove manuals', command=self.remove_manuals).pack(side='left', padx=8)
        ttk.Button(tools, text='Clear chat', command=self.clear_chat).pack(side='right')
        self.manual_label = ttk.Label(frame, wraplength=850)
        self.manual_label.pack(anchor='w', pady=8)
        self.refresh_manuals()
        self.chat = ScrolledText(frame, wrap='word', height=14, state='disabled')
        self.chat.pack(fill='both', expand=True)
        self.append_chat('Assistant', 'Ask about this car, its service history, or an imported manual. Specific specifications need matching source evidence. Sources below each answer show the retrieved excerpts; check them before repairs.')
        self.web = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text='Search the web for this question (sends car name + question to your SearXNG server)', variable=self.web).pack(anchor='w', pady=8)
        entry = ttk.Frame(frame)
        entry.pack(fill='x')
        self.question = ttk.Entry(entry)
        self.question.pack(side='left', fill='x', expand=True)
        self.question.bind('<Return>', lambda event: self.ask())
        ttk.Button(entry, text='Ask', command=self.ask).pack(side='right', padx=(8, 0))

    def append_chat(self, who, text):
        self.chat.configure(state='normal')
        self.chat.insert('end', f'{who}\n{text}\n\n')
        self.chat.configure(state='disabled')
        self.chat.see('end')

    def clear_chat(self):
        if self.busy:
            return
        self.history.clear()
        self.chat.configure(state='normal')
        self.chat.delete('1.0', 'end')
        self.chat.configure(state='disabled')

    def refresh_manuals(self):
        names = self.store.manuals(self.car['id'])
        self.manual_label.configure(text='Manuals: ' + (', '.join(f'{name} ({count} passages)' for name, count in names) or 'None imported'))

    def import_manual(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self, title='Choose the manual for this year / engine / trim', filetypes=[('Manuals', '*.pdf *.txt *.md')])
        if path:
            def done(result):
                self.refresh_manuals()
                self.status.set(result)
                self.history.clear()
                self.append_chat('Manual library', result + ' Conversation context reset for the new manual.')
            self.run_job('Reading and indexing manual…', lambda: self.store.import_manual(self.car['id'], path), done)

    def remove_manuals(self):
        if not self.busy and messagebox.askyesno('Remove manuals?', 'Remove indexed manual text for this car? Original files are kept.', parent=self):
            self.store.remove_manuals(self.car['id'])
            self.history.clear()
            self.refresh_manuals()
            self.append_chat('Manual library', 'Manuals removed; conversation context reset.')

    def ask(self):
        if self.busy:
            return
        question = self.question.get().strip()
        if not question:
            return
        try:
            settings = self.store.settings()
        except ValueError as error:
            messagebox.showerror('AI settings', str(error), parent=self)
            return
        try:
            self.car = copy.deepcopy(self.master.garage.car(self.car['id']))
        except (KeyError, StopIteration, ValueError):
            messagebox.showerror('Car unavailable', 'This car was removed. Close AI Garage and select an existing car.', parent=self)
            return
        history = copy.deepcopy(self.history)
        use_web = self.web.get()
        def done(result):
            self.history.extend([{'role': 'user', 'content': question}, {'role': 'assistant', 'content': result['answer']}])
            self.history = self.history[-12:]
            self.append_chat('Assistant', result['answer'])
            if result['warning']:
                self.append_chat('Retrieval notice', result['warning'])
            if result['sources']:
                lines = []
                for source in result['sources']:
                    location = f"PDF/text page {source['page']}" if 'page' in source else source['url']
                    lines.append(f"[{source['id']}] {source['source']} · {location}\n{source['text']}")
                self.append_chat('Retrieved evidence (not all passages necessarily support the answer)', '\n\n'.join(lines))
            else:
                self.append_chat('Retrieval notice', 'No matching source passages retrieved. This answer is unverified general model knowledge.')
        if self.run_job('Retrieving sources and asking the local model…', lambda: answer_question(self.store, settings, self.car, question, history, use_web), done):
            self.append_chat('You', question)
            self.question.delete(0, 'end')

    def build_portrait(self, frame):
        ttk.Label(frame, text='Generate a studio portrait of your car', font=('Helvetica', 15, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Illustrative AI image; model details may differ from your actual car. Not a rotatable 3D model.', wraplength=850).pack(anchor='w', pady=8)
        ttk.Label(frame, text='Appearance (color, body style, wheels, trim — do not include VIN)').pack(anchor='w')
        self.appearance = ttk.Entry(frame)
        self.appearance.insert(0, 'factory stock, metallic silver')
        self.appearance.pack(fill='x', pady=5)
        self.prompt = ScrolledText(frame, height=5, wrap='word')
        self.prompt.insert('1.0', portrait_prompt(self.car['name'], self.appearance.get()))
        self.prompt.pack(fill='x', pady=6)
        tools = ttk.Frame(frame)
        tools.pack(fill='x')
        ttk.Button(tools, text='Update prompt from appearance', command=self.update_prompt).pack(side='left')
        ttk.Button(tools, text='Generate portrait', command=self.generate).pack(side='left', padx=8)
        self.portrait = ttk.Label(frame, text='No portrait yet. Configure ComfyUI and import an API workflow in AI settings.', anchor='center', wraplength=700)
        self.portrait.pack(fill='both', expand=True, pady=12)
        self.load_portrait()

    def update_prompt(self):
        self.prompt.delete('1.0', 'end')
        self.prompt.insert('1.0', portrait_prompt(self.car['name'], self.appearance.get()))

    def load_portrait(self, result=None):
        path = self.store.portrait_path(self.car['id'])
        if path.exists():
            try:
                image = tk.PhotoImage(file=str(path))
                factor = max(1, (image.width() + 699) // 700, (image.height() + 299) // 300)
                self.portrait_image = image.subsample(factor, factor)
                self.portrait.configure(image=self.portrait_image, text='')
            except tk.TclError:
                self.portrait.configure(text='Saved image could not be displayed. Generate a PNG portrait again.')

    def generate(self):
        if self.busy:
            return
        prompt = self.prompt.get('1.0', 'end').strip()
        if not prompt or len(prompt) > 4000:
            messagebox.showerror('Portrait', 'Enter a prompt between 1 and 4000 characters.', parent=self)
            return
        try:
            settings = self.store.settings()
        except ValueError as error:
            messagebox.showerror('AI settings', str(error), parent=self)
            return
        self.run_job('Generating portrait in ComfyUI… this may take several minutes.',
                     lambda: generate_portrait(self.store, settings, self.car['id'], prompt, self.stopped.is_set), self.load_portrait)

    def build_settings(self, frame):
        ttk.Label(frame, text='Local AI connections', font=('Helvetica', 15, 'bold')).pack(anchor='w', pady=(0, 10))
        try:
            settings = self.store.settings()
        except ValueError as error:
            from ai_garage import DEFAULTS
            settings = DEFAULTS
            ttk.Label(frame, text=str(error), wraplength=850).pack(anchor='w')
        self.setting_entries = {}
        for key, label in [('ollama_url', 'Ollama server URL'), ('chat_model', 'Chat model (exact Ollama tag)'), ('comfy_url', 'ComfyUI server URL'), ('search_url', 'Optional SearXNG server URL (JSON search enabled)')]:
            ttk.Label(frame, text=label).pack(anchor='w', pady=(6, 2))
            entry = ttk.Entry(frame)
            entry.insert(0, settings[key])
            entry.pack(fill='x')
            self.setting_entries[key] = entry
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=14)
        ttk.Button(row, text='Save settings', command=self.save_settings).pack(side='left')
        ttk.Button(row, text='Test Ollama / list models', command=self.test_ollama).pack(side='left', padx=8)
        ttk.Button(frame, text='Import ComfyUI API workflow JSON', command=self.import_workflow).pack(anchor='w', pady=8)
        ttk.Label(frame, text='In ComfyUI: build and test a text-to-image workflow, place {{PROMPT}} in its positive prompt, include SaveImage, then export in API format. Choose an installed checkpoint suitable for your GPU. The app sends this workflow to ComfyUI; it does not install models.\n\nStart with a 7–8B quantized instruction model for chat. Manual retrieval uses SQLite FTS5/BM25 and preserves page references. Model choice is configurable; retrieval does not train or fine-tune the chat model.\n\nWith 16 GB VRAM, run portrait generation separately from chat if memory is tight. Chat includes this car’s notes and recent service records; use a server you trust. Web search sends only the car name and your question. Chat is kept in memory and clears when this window closes.', wraplength=850, justify='left').pack(anchor='w', pady=12)

    def save_settings(self):
        if self.busy:
            return
        try:
            self.store.save_settings({key: entry.get() for key, entry in self.setting_entries.items()})
            self.status.set('AI settings saved locally.')
        except (ValueError, OSError) as error:
            messagebox.showerror('AI settings', str(error), parent=self)

    def test_ollama(self):
        if self.busy:
            return
        try:
            base = endpoint(self.setting_entries['ollama_url'].get())
        except ValueError as error:
            messagebox.showerror('AI settings', str(error), parent=self)
            return
        def done(result):
            names = [item['name'] for item in result.get('models', [])]
            messagebox.showinfo('Ollama models', '\n'.join(names) or 'No models installed. Pull a model with Ollama first.', parent=self)
        self.run_job('Connecting to Ollama…', lambda: request_json(base + '/api/tags', timeout=10), done)

    def import_workflow(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self, title='ComfyUI API-format workflow', filetypes=[('JSON workflow', '*.json')])
        if path:
            try:
                if Path(path).stat().st_size > 2_000_000:
                    raise ValueError('Workflow JSON must be smaller than 2 MB.')
                template = json.loads(Path(path).read_text(encoding='utf-8'))
                prepare_workflow(template, 'validation prompt')
                self.store.atomic_write(self.store.workflow_path(), json.dumps(template, indent=2).encode())
                self.status.set('ComfyUI workflow imported. Ready to generate portraits.')
            except (ValueError, OSError) as error:
                messagebox.showerror('Workflow', str(error), parent=self)
