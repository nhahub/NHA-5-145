# Ticket 13 browser speech smoke test

Browser speech recognition is optional and stays outside deterministic Agent evaluation. The Panel inserts a transcript into the editable request field; the Shopper reviews it and presses **إرسال** to send. Recognition does not execute Shopping Actions or submit a message by itself. When the browser speech service fails, the Panel offers an explicit, at-most-ten-second WebM recording. That recording goes through the local Agent to OpenRouter for transcription only after the Shopper presses the disclosed recording button. It is never submitted as a shopping request automatically.

Run this manual check in a Chromium browser with a working microphone and microphone permission for `http://localhost:4100`:

1. Start the local Storefront, Agent, and Panel. Open the Panel and choose **العربية المصرية**. Press **إدخال صوتي**, grant microphone access, and say `عايز كوتشي جري`. Check the transcript appears in the input, remains editable, and does not submit automatically. Edit it if needed, then press **إرسال**.
2. Choose **English**, press **إدخال صوتي**, and say `Show me running shoes`. Check the English transcript appears and again requires an explicit send.
3. Start listening, then press **إيقاف**. Check listening stops. Repeat while the page is narrow and while a Storefront disclosure or cart dialog is open; Stop must stay reachable.
4. Deny microphone permission once. Check the Panel announces the error and still accepts typed input. In a browser without SpeechRecognition, check the speech button is disabled with an availability hint.
5. In the in-app browser, press **إدخال صوتي**. If browser speech fails with `network`, check that **تسجيل قصير عبر OpenRouter** appears only while the configured key has enough allowance. Read its disclosure, press it to record `عايز كوتشي جري`, then stop. Check the transcript is editable, no shopping task starts, and the microphone indicator turns off. If permission is denied, typed input must remain available.

Record the browser, OS, date, and actual outcomes when a human performs this device check. Automated Panel tests use fake recognition and recording APIs to verify language selection, transcript placement, no auto-submit, allowance gating, and Stop cancellation; they do not prove microphone permission or recognition quality. A short synthetic Arabic WebM recording was transcribed through the live OpenRouter route with the owner's non-resetting $0.75 key cap; the owner's microphone still needs manual verification.
