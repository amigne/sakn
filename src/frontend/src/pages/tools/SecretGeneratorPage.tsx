import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import PageLayout from "@/components/layout/PageLayout";
import ToolForm from "@/components/tool/ToolForm";
import ToolOutput from "@/components/tool/ToolOutput";
import { Alert, ProgressBar, Tabs, TextInput, ToggleSwitch } from "@/components/ui";
import { generateHex, generatePassword, generateToken, SecretGeneratorError } from "@/lib/secretGenerator";
import { useToolStore } from "@/stores/toolStore";
import type { SecretGeneratorMode, SecretGeneratorResult } from "@/types/tool";

const CLIPBOARD_CLEAR_S = 30;
const COPIED_TOAST_MS = 2_000;

/** Check if the Clipboard API is available (HTTPS/localhost). */
function isClipboardAvailable(): boolean {
  return typeof navigator !== "undefined" && !!navigator.clipboard?.writeText;
}

export default function SecretGeneratorPage() {
  const { t } = useTranslation();

  // ── Active tool ──────────────────────────────────────────────────────
  useEffect(() => {
    useToolStore.getState().setActiveTool("secret_generator");
  }, []);

  // ── Mode ─────────────────────────────────────────────────────────────
  const [mode, setMode] = useState<SecretGeneratorMode>("password");

  // ── Password parameters ──────────────────────────────────────────────
  const [passwordLength, setPasswordLength] = useState(20);
  const [uppercase, setUppercase] = useState(true);
  const [lowercase, setLowercase] = useState(true);
  const [digits, setDigits] = useState(true);
  const [symbols, setSymbols] = useState(true);

  // ── Token / Hex parameters ───────────────────────────────────────────
  const [tokenLength, setTokenLength] = useState(43);
  const [hexLength, setHexLength] = useState(64);

  // ── Result & validation ──────────────────────────────────────────────
  const [result, setResult] = useState<SecretGeneratorResult | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // ── Clipboard ────────────────────────────────────────────────────────
  const [copied, setCopied] = useState(false);
  const [clipboardSeconds, setClipboardSeconds] = useState(0);
  const clipboardTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const copiedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Tracks whether this tool wrote the current clipboard contents, so reset()
  // only clears the clipboard it actually populated (never unrelated content).
  const wroteToClipboardRef = useRef(false);

  const clipboardAvailable = isClipboardAvailable();

  // Cleanup all timers on unmount
  useEffect(() => {
    return () => {
      if (clipboardTimerRef.current !== null) clearTimeout(clipboardTimerRef.current);
      if (copiedTimerRef.current !== null) clearTimeout(copiedTimerRef.current);
      if (countdownIntervalRef.current !== null) clearInterval(countdownIntervalRef.current);
    };
  }, []);

  // ── Stop countdown when it reaches 0 ─────────────────────────────────
  useEffect(() => {
    if (clipboardSeconds <= 0 && countdownIntervalRef.current !== null) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
  }, [clipboardSeconds]);

  // ── Validate ─────────────────────────────────────────────────────────
  const validate = useCallback((): boolean => {
    if (mode === "password") {
      if (!uppercase && !lowercase && !digits && !symbols) {
        setValidationError(t("tools.secret_generator.no_charset_selected"));
        return false;
      }
    }
    setValidationError(null);
    return true;
  }, [mode, uppercase, lowercase, digits, symbols, t]);

  // ── Generate ─────────────────────────────────────────────────────────
  const generate = useCallback(() => {
    if (!validate()) return;
    setValidationError(null);

    let res: SecretGeneratorResult;
    try {
      switch (mode) {
        case "password":
          res = generatePassword({
            mode: "password",
            length: passwordLength,
            uppercase,
            lowercase,
            digits,
            symbols,
          });
          break;
        case "token":
          res = generateToken(tokenLength);
          break;
        case "hex":
          res = generateHex(hexLength);
          break;
      }
    } catch (err) {
      // The only SecretGeneratorError code is "no_charset_selected", which
      // validate() already guards for password mode; this is a defensive fallback.
      if (err instanceof SecretGeneratorError) {
        setValidationError(t("tools.secret_generator.no_charset_selected"));
      } else {
        setValidationError(String(err));
      }
      return;
    }

    setResult(res);
    setCopied(false);
    setClipboardSeconds(0);
    if (countdownIntervalRef.current !== null) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, passwordLength, uppercase, lowercase, digits, symbols, tokenLength, hexLength, validate]);

  // ── Reset ────────────────────────────────────────────────────────────
  const reset = useCallback(() => {
    setResult(null);
    setValidationError(null);
    setCopied(false);
    setClipboardSeconds(0);
    if (clipboardTimerRef.current !== null) {
      clearTimeout(clipboardTimerRef.current);
      clipboardTimerRef.current = null;
    }
    if (countdownIntervalRef.current !== null) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    if (copiedTimerRef.current !== null) {
      clearTimeout(copiedTimerRef.current);
      copiedTimerRef.current = null;
    }
    // Clear clipboard only if THIS tool wrote to it (never unrelated content).
    if (clipboardAvailable && wroteToClipboardRef.current) {
      navigator.clipboard.writeText("").catch(() => {});
      wroteToClipboardRef.current = false;
    }
  }, [clipboardAvailable]);

  // ── Copy to clipboard with 30s auto-clear ────────────────────────────
  const copyToClipboard = useCallback(() => {
    if (!result || !clipboardAvailable) return;

    navigator.clipboard
      .writeText(result.secret)
      .then(() => {
        wroteToClipboardRef.current = true;
        setCopied(true);
        setClipboardSeconds(CLIPBOARD_CLEAR_S);

        // Clear "Copied!" toast after 2s
        if (copiedTimerRef.current !== null) clearTimeout(copiedTimerRef.current);
        copiedTimerRef.current = setTimeout(() => setCopied(false), COPIED_TOAST_MS);

        // Schedule clipboard clear after 30s
        if (clipboardTimerRef.current !== null) clearTimeout(clipboardTimerRef.current);
        // Capture the secret value at copy time so the timer callback can
        // compare against it even if `result` changes before the timer fires.
        const copiedSecret = result.secret;
        clipboardTimerRef.current = setTimeout(async () => {
          // Guard: only clear if this tool still "owns" the clipboard.
          if (!wroteToClipboardRef.current) {
            setClipboardSeconds(0);
            return;
          }
          try {
            const current = await navigator.clipboard.readText();
            if (current === copiedSecret) {
              await navigator.clipboard.writeText("");
              wroteToClipboardRef.current = false;
            }
            // If clipboard content does not match, the user has copied
            // something else — leave it alone.
          } catch {
            // Clipboard read permission denied (best-effort: do not clear
            // since we cannot verify ownership).
          }
          setClipboardSeconds(0);
        }, CLIPBOARD_CLEAR_S * 1000);

        // Start countdown interval
        if (countdownIntervalRef.current !== null) clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = setInterval(() => {
          setClipboardSeconds((prev) => {
            if (prev <= 1) return 0;
            return prev - 1;
          });
        }, 1000);
      })
      .catch(() => {});
  }, [result, clipboardAvailable]);

  // ── Update helper ────────────────────────────────────────────────────
  const updateNumber = useCallback(
    (setter: (v: number) => void, min: number, max: number) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setValidationError(null);
      const raw = parseInt(e.target.value, 10);
      if (Number.isNaN(raw)) return;
      setter(Math.max(min, Math.min(max, raw)));
    },
    [],
  );

  // ── Mode tabs ────────────────────────────────────────────────────────
  const modeTabs = [
    { value: "password", label: t("tools.secret_generator.mode_password") },
    { value: "token", label: t("tools.secret_generator.mode_token") },
    { value: "hex", label: t("tools.secret_generator.mode_hex") },
  ];

  const hasResult = result !== null;

  // ── Render ───────────────────────────────────────────────────────────
  return (
    <PageLayout>
      <ToolForm
        title={t("tools.secret_generator.name")}
        isRunning={false}
        onStart={generate}
        onReset={reset}
        startLabel={t("tools.secret_generator.regenerate")}
      >
        {/* Mode tabs — full width */}
        <div className="col-span-full">
          <Tabs
            tabs={modeTabs}
            value={mode}
            onChange={(v) => {
              setMode(v as SecretGeneratorMode);
              setValidationError(null);
            }}
          >
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {mode === "password" && (
                <>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs font-medium text-[var(--color-text-secondary)]">
                      {t("tools.secret_generator.param_length_label")}
                    </span>
                    <TextInput
                      type="number"
                      min={8}
                      max={128}
                      value={passwordLength}
                      onChange={updateNumber(setPasswordLength, 8, 128)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") generate();
                      }}
                    />
                  </div>
                  <div className="flex flex-wrap items-end gap-4">
                    <ToggleSwitch
                      checked={uppercase}
                      onChange={(v) => {
                        setValidationError(null);
                        setUppercase(v);
                      }}
                      label={t("tools.secret_generator.param_uppercase_label")}
                    />
                    <ToggleSwitch
                      checked={lowercase}
                      onChange={(v) => {
                        setValidationError(null);
                        setLowercase(v);
                      }}
                      label={t("tools.secret_generator.param_lowercase_label")}
                    />
                  </div>
                  <div className="flex flex-wrap items-end gap-4">
                    <ToggleSwitch
                      checked={digits}
                      onChange={(v) => {
                        setValidationError(null);
                        setDigits(v);
                      }}
                      label={t("tools.secret_generator.param_digits_label")}
                    />
                    <ToggleSwitch
                      checked={symbols}
                      onChange={(v) => {
                        setValidationError(null);
                        setSymbols(v);
                      }}
                      label={t("tools.secret_generator.param_symbols_label")}
                    />
                  </div>
                </>
              )}

              {mode === "token" && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-[var(--color-text-secondary)]">
                    {t("tools.secret_generator.param_length_token_label")}
                  </span>
                  <TextInput
                    type="number"
                    min={16}
                    max={256}
                    value={tokenLength}
                    onChange={updateNumber(setTokenLength, 16, 256)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") generate();
                    }}
                  />
                </div>
              )}

              {mode === "hex" && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-[var(--color-text-secondary)]">
                    {t("tools.secret_generator.param_length_hex_label")}
                  </span>
                  <TextInput
                    type="number"
                    min={16}
                    max={512}
                    value={hexLength}
                    onChange={updateNumber(setHexLength, 16, 512)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") generate();
                    }}
                  />
                </div>
              )}
            </div>
          </Tabs>
        </div>

        {/* Validation error */}
        {validationError && (
          <div className="col-span-full">
            <Alert variant="error">{validationError}</Alert>
          </div>
        )}
      </ToolForm>

      <ToolOutput
        status={hasResult ? "completed" : "idle"}
        emptyMessage={t("tools.secret_generator.description")}
        onCopy={clipboardAvailable ? copyToClipboard : undefined}
      >
        {/* Fallback when JS is disabled */}
        <noscript>
          <p className="text-sm text-[var(--color-text-secondary)]">{t("tools.secret_generator.js_disabled")}</p>
        </noscript>

        {/* Fallback when Clipboard API is unavailable */}
        {!clipboardAvailable && (
          <p className="text-sm text-[var(--color-text-secondary)] mb-2">
            {t("tools.secret_generator.clipboard_unavailable")}
          </p>
        )}

        {hasResult && (
          <div className="space-y-3" aria-live="polite">
            {/* Secret display — monospace, read-only, selectable */}
            <textarea
              readOnly
              className="w-full p-3 font-mono text-sm bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded resize-none select-all break-all"
              rows={3}
              value={result.secret}
              aria-label={t("tools.secret_generator.name")}
              spellCheck={false}
            />

            {/* Strength indicator */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-[var(--color-text-secondary)] w-20">
                  {t(`tools.secret_generator.strength_${result.strength}`)}
                </span>
                <ProgressBar value={Math.min(result.bits, 256)} max={256} className="flex-1" />
              </div>
              <p className="text-xs text-[var(--color-text-secondary)]">
                {t("tools.secret_generator.entropy", {
                  length: result.actualLength,
                  bits: result.bits,
                })}
              </p>
            </div>

            {/* "Copied!" toast */}
            {copied && (
              <p className="text-sm text-green-600 dark:text-green-400" role="status">
                {t("tools.secret_generator.copied")}
              </p>
            )}

            {/* Auto-clear clipboard countdown */}
            {clipboardSeconds > 0 && (
              <p className="text-xs text-[var(--color-text-secondary)]">
                {t("tools.secret_generator.auto_clear_notice", {
                  seconds: clipboardSeconds,
                })}
              </p>
            )}
          </div>
        )}
      </ToolOutput>
    </PageLayout>
  );
}
