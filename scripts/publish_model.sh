#!/usr/bin/env bash
# Upload the fine-tuned invoice reader (downloaded from the Kaggle run) to a PRIVATE
# Hugging Face model repo. Tokens come from .env via with-env.sh and are never printed.
#   scripts/publish_model.sh
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
model_dir="$here/model/kaggle/output/invoice-reader"
repo="vedanttigade5/borrower-truth-invoice-reader"

[ -d "$model_dir" ] || { echo "no model at $model_dir (download the Kaggle output first)"; exit 1; }
cp "$here/model/kaggle/output/metrics.json" "$model_dir/metrics.json" 2>/dev/null || true
if [ ! -f "$model_dir/README.md" ]; then
  cat > "$model_dir/README.md" <<'EOF'
# Borrower Truth: invoice reader (synthetic demo)

Donut (naver-clova-ix/donut-base), fine-tuned to read invoice number, PO number,
bill-to, date and total from invoice images. Trained and tested ONLY on synthetic
invoices generated for the Borrower Truth project. Not for use on real documents
without re-validation. Metrics: metrics.json (held-out borrowers).
EOF
fi
"$here/scripts/with-env.sh" hf repo create "$repo" --repo-type model --private --exist-ok 2>&1 | grep -v -i token || true
"$here/scripts/with-env.sh" hf upload "$repo" "$model_dir" . --repo-type model --private 2>&1 | grep -v -i token | tail -3
echo "published privately: https://huggingface.co/$repo"
