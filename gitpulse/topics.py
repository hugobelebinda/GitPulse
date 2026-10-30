"""Curated engineering topics tracked by GitPulse.

Each topic matches public GitHub events by exact seed repos and/or
case-insensitive substrings in repo_name. Patterns stay intentional and
narrow so daily aggregates stay interpretable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    slug: str
    label: str
    keywords: tuple[str, ...]
    seed_repos: tuple[str, ...]


TOPICS: tuple[Topic, ...] = (
    Topic(
        "python",
        "Python",
        ("/python", "cpython", "django", "fastapi", "flask", "pytorch", "pandas"),
        ("python/cpython", "pallets/flask", "encode/httpx", "tiangolo/fastapi"),
    ),
    Topic(
        "rust",
        "Rust",
        ("/rust", "rust-", "rustlang", "tokio", "serde"),
        ("rust-lang/rust", "tokio-rs/tokio", "serde-rs/serde"),
    ),
    Topic(
        "typescript",
        "TypeScript",
        ("typescript", "next.js", "nextjs", "nestjs"),
        ("microsoft/TypeScript", "vercel/next.js", "nestjs/nest"),
    ),
    Topic(
        "golang",
        "Go",
        ("/go-", "golang", "gin-gonic"),
        ("golang/go", "gin-gonic/gin", "uber-go/zap"),
    ),
    Topic(
        "kubernetes",
        "Kubernetes",
        ("kubernetes", "k8s", "helm-", "/helm"),
        ("kubernetes/kubernetes", "helm/helm", "kubernetes/ingress-nginx"),
    ),
    Topic(
        "llm",
        "LLM / GenAI",
        ("langchain", "llama", "ollama", "vllm", "openai", "huggingface", "transformers"),
        ("langchain-ai/langchain", "ollama/ollama", "vllm-project/vllm", "huggingface/transformers"),
    ),
    Topic(
        "devops",
        "DevOps / CI",
        ("terraform", "ansible", "github-actions", "prometheus", "grafana"),
        ("hashicorp/terraform", "ansible/ansible", "prometheus/prometheus", "grafana/grafana"),
    ),
    Topic(
        "security",
        "Security",
        ("cve", "trivy", "falco", "owasp", "security"),
        ("aquasecurity/trivy", "falcosecurity/falco", "OWASP/CheatSheetSeries"),
    ),
    Topic(
        "databases",
        "Databases",
        ("postgres", "postgresql", "clickhouse", "mongodb", "redis", "sqlite"),
        ("postgres/postgres", "ClickHouse/ClickHouse", "redis/redis", "mongodb/mongo"),
    ),
    Topic(
        "web3",
        "Web3",
        ("ethereum", "solidity", "web3", "bitcoin"),
        ("ethereum/go-ethereum", "bitcoin/bitcoin"),
    ),
    Topic(
        "java",
        "Java",
        ("/java", "spring-boot", "springboot", "maven", "gradle"),
        ("openjdk/jdk", "spring-projects/spring-boot", "apache/maven"),
    ),
    Topic(
        "csharp",
        ".NET / C#",
        ("dotnet", ".net", "csharp", "aspnet"),
        ("dotnet/runtime", "dotnet/aspnetcore", "dotnet/roslyn"),
    ),
    Topic(
        "cpp",
        "C / C++",
        ("/cpp", "cplusplus", "llvm", "cmake"),
        ("llvm/llvm-project", "fmtlib/fmt", "nlohmann/json"),
    ),
    Topic(
        "ruby",
        "Ruby",
        ("/ruby", "rails", "rubygems"),
        ("ruby/ruby", "rails/rails", "rubygems/rubygems"),
    ),
    Topic(
        "php",
        "PHP",
        ("/php", "laravel", "symfony", "composer"),
        ("php/php-src", "laravel/framework", "symfony/symfony"),
    ),
    Topic(
        "swift",
        "Swift",
        ("/swift", "swiftui", "swift-nio"),
        ("apple/swift", "vapor/vapor", "Alamofire/Alamofire"),
    ),
    Topic(
        "kotlin",
        "Kotlin",
        ("kotlin", "ktor", "compose-multiplatform"),
        ("JetBrains/kotlin", "ktorio/ktor", "android/compose-multiplatform"),
    ),
    Topic(
        "scala",
        "Scala",
        ("/scala", "akka", "zio-", "/zio"),
        ("scala/scala", "apache/spark", "zio/zio"),
    ),
    Topic(
        "zig",
        "Zig",
        ("/zig", "ziglang"),
        ("ziglang/zig",),
    ),
    Topic(
        "wasm",
        "WebAssembly",
        ("webassembly", "wasmtime", "wasmer", "wasm-"),
        ("WebAssembly/spec", "bytecodealliance/wasmtime", "wasmerio/wasmer"),
    ),
    Topic(
        "react",
        "React",
        ("/react", "reactjs", "react-native", "remix-run"),
        ("facebook/react", "remix-run/remix", "TanStack/query"),
    ),
    Topic(
        "vue",
        "Vue",
        ("/vue", "vuejs", "nuxt", "vitejs"),
        ("vuejs/core", "nuxt/nuxt", "vitejs/vite"),
    ),
    Topic(
        "docker",
        "Docker / Containers",
        ("docker", "containerd", "podman", "buildkit"),
        ("moby/moby", "containerd/containerd", "containers/podman"),
    ),
    Topic(
        "aws",
        "AWS / Cloud",
        ("aws-", "amazonaws", "terraform-aws", "cdk"),
        ("aws/aws-cli", "aws/aws-cdk", "hashicorp/terraform-provider-aws"),
    ),
    Topic(
        "dataeng",
        "Data Engineering",
        ("airflow", "dbt-", "dbt_", "spark", "prefect", "dagster"),
        ("apache/airflow", "dbt-labs/dbt-core", "apache/spark", "dagster-io/dagster"),
    ),
    Topic(
        "ml",
        "Classical ML",
        ("scikit-learn", "sklearn", "xgboost", "lightgbm", "catboost"),
        ("scikit-learn/scikit-learn", "dmlc/xgboost", "microsoft/LightGBM"),
    ),
    Topic(
        "observability",
        "Observability",
        ("opentelemetry", "otel", "jaeger", "tempo", "loki"),
        ("open-telemetry/opentelemetry-collector", "jaegertracing/jaeger", "grafana/loki"),
    ),
    Topic(
        "mobile",
        "Mobile",
        ("flutter", "react-native", "android", "ios-", "expo"),
        ("flutter/flutter", "facebook/react-native", "expo/expo"),
    ),
    Topic(
        "elixir",
        "Elixir",
        ("/elixir", "phoenix", "erlang"),
        ("elixir-lang/elixir", "phoenixframework/phoenix", "erlang/otp"),
    ),
    Topic(
        "streaming",
        "Streaming",
        ("kafka", "flink", "pulsar", "redpanda", "nats-"),
        ("apache/kafka", "apache/flink", "apache/pulsar", "nats-io/nats-server"),
    ),
)


TOPIC_BY_SLUG = {topic.slug: topic for topic in TOPICS}


def match_topic_slugs(repo_name: str) -> list[str]:
    name = (repo_name or "").lower()
    if not name:
        return []
    hits: list[str] = []
    for topic in TOPICS:
        if name in {repo.lower() for repo in topic.seed_repos}:
            hits.append(topic.slug)
            continue
        if any(keyword.lower() in name for keyword in topic.keywords):
            hits.append(topic.slug)
    return hits
