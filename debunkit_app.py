import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import ImageTk, Image  
from transformers import pipeline
import threading
import os

class DebunkItApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DebunkIt - Full Analysis Viewer")
        self.root.state('zoomed')  
        self.root.configure(bg="#f5f7fa")
        
        self.text_font = ("Segoe UI", 12)
        self.analysis_font = ("Segoe UI", 11)
        self.max_char_width = 120 
        
        # Add these lines for logo and title
        self.setup_header()
        self.setup_ui()
        self.load_model()
    
    def setup_header(self):
        """Create the header with logo and title"""
        header_frame = tk.Frame(self.root, bg="#4a6fa5")
        header_frame.pack(fill="x", padx=0, pady=0)
        
        try:
            logo_img = Image.open("logo.png")
            logo_img = logo_img.resize((50, 50), Image.LANCZOS)
            self.logo = ImageTk.PhotoImage(logo_img)
            
            logo_label = tk.Label(header_frame, image=self.logo, bg="#4a6fa5")
            logo_label.pack(side="left", padx=(20, 10), pady=10)
        except Exception as e:
            print(f"Logo not found: {e}")
            logo_label = tk.Label(header_frame, text="🧐", font=("Segoe UI", 24), bg="#4a6fa5", fg="white")
            logo_label.pack(side="left", padx=(20, 10), pady=10)

        title_label = tk.Label(header_frame, 
                             text="DebunkIt - Misinformation Detection Tool",
                             font=("Segoe UI", 20, "bold"),
                             bg="#4a6fa5",
                             fg="white")
        title_label.pack(side="left", pady=10)
    
    def setup_ui(self):

        main_frame = tk.Frame(self.root, bg="#f5f7fa")
        main_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Input
        input_frame = tk.LabelFrame(main_frame, 
                                  text=" News Content Input ",
                                  font=("Segoe UI", 14, "bold"),
                                  bg="#ffffff",
                                  padx=15,
                                  pady=15)
        input_frame.pack(fill="x", pady=(0, 20))
        
        self.text_input = scrolledtext.ScrolledText(input_frame,
                                                  wrap=tk.WORD,
                                                  font=self.text_font,
                                                  width=self.max_char_width,
                                                  height=10,
                                                  padx=10,
                                                  pady=10)
        self.text_input.pack(fill="both", expand=True)
        
        # Button
        analyze_btn = tk.Button(main_frame,
                              text="Analyze Content",
                              command=self.analyze,
                              font=("Segoe UI", 12, "bold"),
                              bg="#4a6fa5",
                              fg="white",
                              padx=20,
                              pady=8)
        analyze_btn.pack(pady=10)
        
        result_frame = tk.LabelFrame(main_frame,
                                   text=" Detailed Analysis ",
                                   font=("Segoe UI", 14, "bold"),
                                   bg="#ffffff",
                                   padx=15,
                                   pady=15)
        result_frame.pack(fill="both", expand=True)
        
        self.result_display = scrolledtext.ScrolledText(result_frame,
                                                      wrap=tk.WORD,
                                                      font=self.analysis_font,
                                                      width=self.max_char_width,
                                                      height=15,
                                                      padx=10,
                                                      pady=10,
                                                      state='normal')
        self.result_display.pack(fill="both", expand=True)        
        self.result_display.insert(tk.END, 
                                 "Analysis results will appear here with complete details...\n\n"
                                 )
        self.result_display.configure(state='disabled')
        self.status_bar = tk.Label(self.root,
                                 text="🔄 Loading AI detection model...",
                                 font=("Segoe UI", 10),
                                 bd=1,
                                 relief="sunken",
                                 anchor="w")
        self.status_bar.pack(fill="x", side="bottom")

    def load_model(self):
        def _load():
            try:
                self.detector = pipeline(
                    "text-classification",
                    model="distilbert-base-uncased-finetuned-sst-2-english"
                )
                self.model_loaded = True
                self.status_bar.config(text="✅ Model Ready | Scroll to view full analysis", fg="green")
            except Exception as e:
                messagebox.showerror("Error", f"Model loading failed:\n{e}")
                self.status_bar.config(text="❌ Model Failed to Load", fg="red")
        
        threading.Thread(target=_load, daemon=True).start()
    
    def analyze(self):
        if not hasattr(self, 'model_loaded') or not self.model_loaded:
            messagebox.showwarning("Warning", "AI model is still loading. Please wait.")
            return
        
        text = self.text_input.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter some text to analyze!")
            return
        
        try:
            result = self.detector(text)[0]
            self.result_display.configure(state='normal')
            self.result_display.delete("1.0", tk.END)
            
            if result['label'] == "NEGATIVE":
                analysis = (
                    "⚠️ POTENTIAL MISINFORMATION DETECTED\n\n"
                    f"Confidence Level: {result['score']*100:.1f}%\n\n"
                    "Detailed Analysis:\n"
                    "• Emotionally charged language detected\n"
                    "• Contains exaggerated or absolute claims\n"
                    "• Lacks verifiable sources or references\n"
                    "• Shows patterns consistent with known misinformation\n\n"
                    "Recommendations:\n"
                    "1. Cross-check claims with reliable fact-checking websites\n"
                    "2. Look for primary sources or official statements\n"
                    "3. Be cautious of emotional manipulation techniques"
                )
                self.result_display.tag_config("warning", foreground="red")
                self.result_display.insert(tk.END, analysis, "warning")
            else:
                analysis = (
                    "✅ CREDIBLE CONTENT\n\n"
                    f"Confidence Level: {result['score']*100:.1f}%\n\n"
                    "Detailed Analysis:\n"
                    "• Neutral and factual tone detected\n"
                    "• Claims appear reasonable and measured\n"
                    "• Consistent with established knowledge\n"
                    "• Shows characteristics of reliable information\n\n"
                    "Recommendations:\n"
                    "1. Still verify with primary sources when possible\n"
                    "2. Check the date of publication for relevance\n"
                    "3. Consider the author's credentials and reputation"
                )
                self.result_display.tag_config("safe", foreground="green")
                self.result_display.insert(tk.END, analysis, "safe")
            
            self.result_display.configure(state='disabled')
            self.status_bar.config(text="✔️ Analysis complete - Scroll to read full details")
            
        except Exception as e:
            messagebox.showerror("Error", f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DebunkItApp(root)
    root.mainloop()
