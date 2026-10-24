"""Pixel forensics (Layer D) and AI-generation signal (Layer E) (TRD §9.2).

All findings are `forensic_signal` with the message prefix "Preliminary indicator:".
Skip a document entirely if its pdf_signature check is `verified`.

TODO(question): CheckResult.doc_id is required but TRD §9.2 gives `fn(image_path, regions)`;
how do these functions learn the doc_id?
"""
