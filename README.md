# AISEED 파이썬 프로젝트 템플릿

## 소개

AI 회사인 AISEED는 파이썬 프로젝트가 많습니다.  
이전과 달리, 연구를 넘어 실제 제품까지 만들기 때문에 유지보수가 필요합니다.

우리는 앞으로 **코드 작성** 이외에도 **코드 관리**까지 힘써야 한다는 뜻입니다.  
하지만 프로젝트 유지보수는 쉽지 않습니다.

- 코드 컨벤션 통일
- 프로젝트 구조 설계
- 테스트 코드 작성
- 가상 환경 및 의존성 관리
- ...

신규 프로젝트를 시작할 때, 혹은 새로운 인력이 프로젝트에 투입됐을 때, 매번 위와 같은 요소들을 설명하고 설정하는 일은 비효율적입니다.

그래서 전사 차원에서 사용할 일관된 템플릿을 만들었습니다.

## 구성요소

템플릿에 사용된 기본적인 구성 요소는 다음과 같습니다.

- [rye](https://rye.astral.sh/guide/) - 프로젝트 및 패키지 관리
- [ruff](https://docs.astral.sh/ruff/) - 코드 규칙 및 포맷
- [mypy](https://mypy.readthedocs.io/en/stable/) - 타입 지원
- [pytest](https://docs.pytest.org/) - 테스트 코드
- [pre-commit](https://pre-commit.com/) - git commit 작업 시 사전 작업 수행

## 시작하기

### 개발 환경 설정

- `rye`를 설치해주세요. ([설치 가이드](https://rye.astral.sh/guide/installation/))

### 프로젝트 설정

- Github에서 이 템플릿으로 Repository를 생성한 후 Clone 해주세요.
  ![Github Repository's Use this template](./assets/use-this-template.jpeg)
- 프로젝트 폴더 안에 있는 `pyproject.toml` 파일의 `name`, `version`, `description`, `authors`를 각자의 프로젝트에 맞게 수정해주세요.
- 프로젝트 루트 경로에서 다음 스크립트를 실행해주세요.
  ```bash
  $ rye sync
  $ pre-commit install # 오류 발생 시 터미널을 다시 시작해보세요
  ```

### 메인 함수 실행

`app` 패키지의 main 함수를 실행합니다.

```bash
$ rye run app
```

터미널에 "Hello, AISEED" 메시지가 출력됐다면 성공입니다!

## 프로젝트 지침

### 의존성 관리

의존성을 다룰 때 역시 `pip` 대신 `rye`를 사용합니다.  
개발에 필요한 패키지와 제품에 필요한 패키지를 구분해주세요.

```bash
# install production dependency
$ rye add numpy

# uninstall production dependency
$ rye remove numpy

# install development dependency
$ rye add --dev pytest

# uninstall development dependency
$ rye remove --dev pytest
```

### 타입 체크

`mypy`로 타입 오류가 발생한 지점을 찾습니다.

```bash
$ rye run type
```

### Lint

`ruff`로 코드 컨벤션에 문제가 있는 지점을 찾습니다.

```bash
$ rye run lint
```

### 테스트 실행

`pytest`로 `tests/` 폴더에 있는 테스트를 실행합니다.

```bash
# run test
$ rye run test

# run test with duration
$ rye run test:duration
```

**테스트 코드 작성**은 몹시 어렵고 방대한 주제이기 때문에 테스트 코드 작성법에 대해선 아직 다루지 않습니다.  
대신, 다른 구성원이 쉽게 코드를 파악할 수 있도록 **코드 사용법**을 위주로 작성해주시기 바랍니다.

### Git

작업 내역을 `commit`할 때 `pre-commit`을 이용해 코드를 검사합니다.  
아직은 ruff로 코드 컨벤션만 검사합니다.

\*추후 pytest, mypy까지 수행 예정

[추가 작성 필요]

## 기타

### 프로젝트 환경 확인

```bash
$ rye show
```

### 실행할 수 있는 스크립트 목록 확인

```bash
$ rye run
```

### 스크립트 관리

`pyproject.toml`의 `[tool.rye.scripts]` 항목에 원하는 스크립트를 추가하거나 수정하시면 됩니다.

### 파이썬 버전 변경

1. `.python-version`에서 원하는 버전으로 수정

   (타겟 버전은 `pyproject.toml`의 `requires-version`을 수정)

2. sync 스크립트 실행

   ```bash
   $ rye sync
   ```
