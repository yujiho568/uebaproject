import React, { useMemo, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";

// Single-file step-by-step Guide
// - Shows one step at a time
// - "Next" button to proceed, "Back" to return
// - Progress bar + keyboard nav (Enter/→ for next, ← for back)
// - Replace the sample steps with your own content

export default function Guide() {
  const steps = useMemo(
    () => [
      {
        id: "intro",
        title: "Terraform 설치",
        body: (
          <div className="space-y-3 text-gray-700">
            <p>
              <a
                href="https://console.aws.amazon.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 underline hover:text-blue-800"
              >
                AWS Console
              </a>
              에 접속하여 테라폼을 설치합니다.
            </p>
            <img
              width="100%"
              src="/step1.png"
              alt="Terraform installation screenshot"
              className="rounded-xl border shadow-sm w-full max-w-full h-auto object-contain"
            />
            <pre className="bg-gray-50 rounded-xl p-4 overflow-auto" style={{ fontSize: "18px" }}>
              {`
curl -fsSL -o terraform.zip https://releases.hashicorp.com/terraform/1.9.5/terraform_1.9.5_linux_amd64.zip
unzip terraform.zip
sudo mv terraform /usr/local/bin/
terraform -v
`}
            </pre>
            {/* <ul className="list-disc pl-5">
              <li>AWS account with admin (or required) permissions</li>
              <li>Terraform CLI installed (1.6+ recommended)</li>
              <li>Configured AWS credentials (e.g., via <code>aws configure</code>)</li>
            </ul> */}
          </div>
        ),
      },
      {
        id: "scaffold",
        title: "Zip 파일 다운로드 및 CloudShell에 업로드",
        body: (
          <div className="space-y-3 text-gray-700">
            <a
              href="/UEBA.zip"
              download
              className="inline-block px-4 py-2 rounded-2xl bg-gray-900 text-white hover:opacity-90"
            >
              📦 Download UEBA.zip
            </a>
            <p>
              버튼을 클릭하여 zip 파일을 다운로드한 후, AWS CloudShell에 업로드합니다.
            </p>
          </div>
        ),
      },
      {
        id: "resources",
        title: "Zip 파일 압축 해제 및 Terraform 적용",
        body: (
          <div className="space-y-3 text-gray-700">
            <p>
              업로드한 zip 파일의 압축을 해제하고, Terraform을 적용합니다.
            </p>
            <pre className="bg-gray-50 rounded-xl p-4 overflow-auto text-sm">
              {`unzip UEBA.zip
cd UEBA
terraform init

# 1) 테이블(ingest)만 먼저 생성
terraform apply -target=module.ct_ingest -auto-approve

# 2) 나머지 전체 적용
terraform apply -auto-approve

`}
            </pre>
          </div>
        ),
      },
      {
        id: "apply",
        title: "Docker Image 빌드 및 ECR 푸시",
        body: (
          <div className="space-y-3 text-gray-700">
            <img
              width="100%"
              src="/step4.png"
              alt="Terraform installation screenshot"
              className="rounded-xl border shadow-sm w-full max-w-full h-auto object-contain"
            />
            <p>그림과 같은 오류가 발생 시 Docker 이미지 빌드 후 ECR에 푸시합니다.</p>
            <pre className="bg-gray-50 rounded-xl p-4 overflow-auto text-sm">
              {`terraform output -raw ecr_repository_url
`}
            </pre>
            <p>위 명령어를 통해 ECR 레포지토리의 주소를 알아냅니다.</p>
            <a
              href="/processing_container.zip"
              download
              className="inline-block px-4 py-2 rounded-2xl bg-gray-900 text-white hover:opacity-90"
            >📦 Download processing_container.zip</a>
            <p>먼저 processing_container.zip 파일을 로컬에 다운로드 및 압축 해제 후, Docker 이미지를 빌드하고 ECR에 푸시합니다..</p>
            <pre className="bg-gray-50 rounded-xl p-4 overflow-auto" style={{ fontSize: "13px" }}>

              {`unzip processing_container.zip
cd processing_container

aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin {ECR 레포지토리 주소 중 /ct-pipeline-IAM 사용자 부분을 지움}

REPO={ECR 레포지토리 주소}

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -t \${REPO}:latest \
  --push \
  ./

`}
            </pre>
            <img
              width="100%"
              src="/step4-1.png"
              alt="Terraform installation screenshot"
              className="rounded-xl border shadow-sm w-full max-w-full h-auto object-contain"
            />
            <a
              href="/realtime_container.zip"
              download
              className="inline-block px-4 py-2 rounded-2xl bg-gray-900 text-white hover:opacity-90"
            >📦 Download realtime_container.zip</a>
            <p>다음으로 realtime_container.zip 파일을 로컬에 다운로드 및 압축 해제 후, Docker 이미지를 빌드하고 ECR에 푸시합니다.</p>
            <pre className="bg-gray-50 rounded-xl p-4 overflow-auto" style={{ fontSize: "15px" }}>
              {`unzip realtime_container.zip
cd realtime_container

REPO={ECR 레포지토리 주소에서 마지막 ct-pipeline을 ct-realtime-infer로 교체}

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -t \${REPO}:latest \
  --push \
  ./

`}
            </pre>
            <img
              width="100%"
              src="/step4-2.png"
              alt="Terraform installation screenshot"
              className="rounded-xl border shadow-sm w-full max-w-full h-auto object-contain"
            />
          </div>
        ),
      },
      {
        id: "scaffold",
        title: "UEBA 구축 완료",
        body: (
          <div className="space-y-3 text-gray-700">
            <p>모든 작업이 완료되면 마지막으로 Terraform을 적용합니다.</p>
            <pre className="bg-gray-50 rounded-xl p-4 overflow-auto text-sm">
              {`terraform apply
`}
            </pre>
            <p>
              마지막 terraform apply가 완료되면 UEBA 구축이 완료됩니다.
            </p>
            <img
              width="100%"
              src="/step5.png"
              alt="Terraform installation screenshot"
              className="rounded-xl border shadow-sm w-full max-w-full h-auto object-contain"
            />
          </div>
        ),
      },
    ],
    []
  );

  const [index, setIndex] = useState(0);
  const atStart = index === 0;
  const atEnd = index === steps.length - 1;
  const progress = Math.round((index / (steps.length - 1)) * 100);

  const next = useCallback(() => setIndex((i) => Math.min(i + 1, steps.length - 1)), [steps.length]);
  const prev = useCallback(() => setIndex((i) => Math.max(i - 1, 0)), []);
  const restart = useCallback(() => setIndex(0), []);

  return (
    <div
      className="page mx-auto max-w-3xl p-6"
      tabIndex={0}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === "ArrowRight") && !atEnd) next();
        if (e.key === "ArrowLeft" && !atStart) prev();
      }}
      aria-live="polite"
    >
      <header className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold tracking-tight">AWS Cloud상에 UEBA 설치 방법</h2>
        <span className="text-sm text-gray-600">Step {index + 1} / {steps.length}</span>
      </header>

      {/* Progress Bar */}
      <div className="mt-4">
        <div className="h-2 w-full rounded-full bg-gray-200">
          <motion.div
            className="h-2 rounded-full bg-gray-900"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ type: "tween", duration: 0.25 }}
            aria-label={`Progress: ${progress}%`}
          />
        </div>
      </div>

      {/* Step Card */}
      <div className="mt-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={steps[index].id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2 }}
            className="rounded-2xl border bg-white p-6 shadow-sm"
          >
            <h2 className="text-xl font-medium">{steps[index].title}</h2>
            <div className="mt-3">{steps[index].body}</div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Nav Buttons */}
      {/* Nav Buttons */}
      <div className="mt-6 flex w-full justify-between px-6">
        <button
          type="button"
          onClick={prev}
          disabled={atStart}
          className="h-12 w-32 rounded-md bg-blue-900 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-800 shadow-sm"
        >
          Back
        </button>

        {atEnd ? (
          <button
            type="button"
            onClick={restart}
            className="h-12 w-32 rounded-md bg-blue-900 text-white font-medium hover:bg-blue-800 shadow-sm"
          >
            Start Over
          </button>
        ) : (
          <button
            type="button"
            onClick={next}
            className="h-12 w-32 rounded-md bg-blue-900 text-white font-medium hover:bg-blue-800 shadow-sm"
          >
            Next
          </button>
        )}
      </div>


      {/* Small helper text */}
      {/* <p className="mt-3 text-xs text-gray-500">Tip: Press <kbd>Enter</kbd> or <kbd>→</kbd> to go next, <kbd>←</kbd> to go back.</p> */}
    </div>
  );
}
