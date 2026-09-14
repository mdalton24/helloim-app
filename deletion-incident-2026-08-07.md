# Mass working-tree deletion — 2026-08-07 ~23:29-23:31

Found while checking why the board restart was requested. NOTHING was staged
and every path below is tracked in HEAD, so all content was recoverable from
git. Recorded BEFORE restoring, so the scope is on the record.

Repo root mtimes bracketing the event:
  JARVIS           2026-08-07 23:29:58
  voice-visualizer 2026-08-07 23:31:29
  private_handler.py written 23:30; board restarted 23:36 on Mark's word.

## /home/mdalton/voice-line
    client/test_access.py
    client/test_ears.py
    client/test_failover.py
    client/test_redact.py
    client/test_turn_identity.py
    client/test_upload_types.py
    client/test_wake_word.py
    server/local_brain_server.py
    server/local_brain_server_test.py
    server/test_access_guard.py
    server/test_team_ledger_hooks.py
    server/test_turn_identity_lifetime.py
    systemd/backup-2026-08-03/voiceline-whisper.service.cpu-original
    systemd/test-health-sample
    systemd/units/voiceline-local-brain.service
    systemd/warm-gpu-shaders

## /home/mdalton/voice-visualizer
    assets/sample.html
    assets/samples.html
    hermes.py
    shots/alert.png
    shots/boot.png
    shots/browser-input-live.png
    shots/browser-input-remote.png
    shots/idle.png
    shots/listening.png
    shots/mic-button.png
    shots/mic-panel.png
    shots/mkharness.py
    shots/mkstall.py
    shots/public.png
    shots/shoot.sh
    shots/shootstall.sh
    shots/speaking-peak.png
    shots/speaking.png
    shots/thinking.png
    shots/transcript.png
    shots/wave-2900.png
    shots/wave-2950.png
    shots/wave-3050.png
    shots/wave-3100.png
    shots/wave-3200.png
    shots/wave-3250.png
    shots/welcome.png
    shots/wren-2026-08-03/FINAL-1920x1200.png
    shots/wren-2026-08-03/c-failed500.png
    shots/wren-2026-08-03/c-limbo.png
    shots/wren-2026-08-03/c-recorded.png
    shots/wren-2026-08-03/c-sending.png
    shots/wren-2026-08-03/c-timeout.png
    shots/wren-2026-08-03/f-1366x768.png
    shots/wren-2026-08-03/fresh-1920.png
    shots/wren-2026-08-03/s-broken2.png
    shots/wren-2026-08-03/s-downone.png
    shots/wren-2026-08-03/s-nosvc2.png
    shots/wren-2026-08-03/s-sysdown3.png
    status-sample.html
    test_accounts.py
    test_accounts_http.py
    test_clear.py
    test_decisions.py
    test_questions.py
    test_team_ledger.py

## /home/mdalton/Documents/JARVIS
    test_drift_check.py
    test_hooks.py

## /home/mdalton/markdalton-site
    test_edge_source.py
    test_edge_worker.py
    test_log_record.py
    test_talk_deploy.py
    test_talk_endpoint.py
    test_updates_endpoint.py

## Not tests — live source caught in the same sweep
    voice-visualizer/hermes.py                  imported by server.py (chat); board
                                                restarted at 23:36 with _hermes = None
    voice-line/server/local_brain_server.py     unit inactive, so no live break
    voice-line/systemd/units/voiceline-local-brain.service
