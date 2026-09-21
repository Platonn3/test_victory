# AGENTS.md

## 1. Цель проекта

Нужно реализовать тестовое приложение для автоматической сверки банковских поступлений со счетами.

Сейчас входные данные представлены банковской выпиской в CSV и реестром счетов в XLSX, но архитектура должна быть рассчитана на дальнейшее расширение: другие форматы банковских выписок, API банков, 1С, CRM, Google Sheets и другие источники.

Главная цель — не написать одноразовый скрипт под конкретные файлы августа 2026, а построить небольшой расширяемый reconciliation-сервис с понятными границами между доменной логикой, источниками данных и представлением.

Приоритеты:

1. Корректность финансовой логики.
2. Детерминированность и объяснимость matching.
3. Расширяемость по источникам данных и правилам сопоставления.
4. Тестируемость.
5. Простота запуска и ревью.
6. Отсутствие overengineering.

---

## 2. Основной технический стек

Использовать:

- Python 3.12+
- FastAPI
- Jinja2 для server-side UI
- `uv` как package manager и runner
- `pandas` и/или `openpyxl` только внутри adapter/infrastructure layer
- `pytest`
- `ruff`
- `mypy`
- Docker
- Docker Compose
- Makefile

Не использовать без реальной необходимости:

- React / отдельный frontend project
- Celery
- Kafka
- Redis
- PostgreSQL
- Kubernetes
- отдельные микросервисы
- сложный DI framework

Проект должен быть модульным монолитом.

---

## 3. Package management: uv

`uv` является обязательным package manager.

Ожидаемые файлы:

```text
pyproject.toml
uv.lock
```

Основные команды должны быть доступны напрямую и через Makefile.

Примеры допустимых внутренних команд:

```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy app
```

Но в README основной пользовательский путь должен быть через Makefile, чтобы reviewer не обязан был помнить команды `uv`, `docker compose` и `pytest`.

---

## 4. Запуск проекта

Проект должен запускаться через Docker Compose.

Основной пользовательский сценарий:

```bash
make up
```

После этого приложение должно быть доступно на:

```text
http://localhost:8000
```

Минимальные Makefile-команды:

```text
make install
make build
make up
make down
make restart
make logs
make test
make lint
make typecheck
make format
make check
```

`make check` должен запускать как минимум:

```text
ruff check
mypy
pytest
```

Makefile является основным human-friendly interface к dev-командам.

---

## 5. Архитектурный стиль

Использовать lightweight hexagonal / clean architecture.

Высокоуровневая схема:

```text
                    FastAPI / Web
                         |
                         v
                  Application layer
                         |
                         v
                Reconciliation use case
                         |
          +--------------+--------------+
          |                             |
          v                             v
      Domain core                    Ports
          ^                             ^
          |                             |
          +-------------+---------------+
                        |
                     Adapters
```

Ключевой принцип:

> Domain и application layer не должны знать, что такое CSV, XLSX, pandas, FastAPI, Docker или Jinja2.

---

## 6. Предпочтительная структура проекта

```text
.
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── reconciliation.py
│   │   │   └── health.py
│   │   └── schemas/
│   │
│   ├── application/
│   │   ├── services/
│   │   │   └── reconciliation.py
│   │   └── dto/
│   │
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── invoice.py
│   │   │   ├── payment.py
│   │   │   └── allocation.py
│   │   │
│   │   ├── matching/
│   │   │   ├── engine.py
│   │   │   └── rules/
│   │   │       ├── explicit_invoice.py
│   │   │       ├── multiple_invoices.py
│   │   │       └── inn_amount.py
│   │   │
│   │   └── reconciliation/
│   │       ├── result.py
│   │       └── validator.py
│   │
│   ├── ports/
│   │   ├── payment_source.py
│   │   ├── invoice_source.py
│   │   └── report_exporter.py
│   │
│   ├── adapters/
│   │   ├── payment_sources/
│   │   │   └── bank_csv.py
│   │   ├── invoice_sources/
│   │   │   └── excel.py
│   │   └── reports/
│   │       └── excel.py
│   │
│   ├── bootstrap/
│   │   └── dependencies.py
│   │
│   ├── templates/
│   └── static/
│
├── tests/
│   ├── unit/
│   │   ├── matching/
│   │   ├── parsers/
│   │   └── reconciliation/
│   └── integration/
│       └── test_reconciliation.py
│
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── uv.lock
├── README.md
└── .env.example
```

Структуру можно немного адаптировать, но нельзя превращать проект в набор `utils.py`, `helpers.py` и одного большого `services.py`.

---

## 7. Ports и adapters

Не создавать интерфейсы вокруг конкретного формата файла вроде `CsvParser` как основной абстракции системы.

Абстракция должна отражать бизнес-роль источника.

Предпочтительно:

```python
from typing import Protocol

class PaymentSource(Protocol):
    def load(self, source: object) -> "PaymentBatch": ...


class InvoiceSource(Protocol):
    def load(self, source: object) -> "InvoiceBatch": ...


class ReportExporter(Protocol):
    def export(self, result: "ReconciliationResult") -> bytes: ...
```

Конкретные реализации:

```text
PaymentSource
    -> BankCsvPaymentSource
    -> FutureBankApiPaymentSource
    -> FutureOneCPaymentSource

InvoiceSource
    -> ExcelInvoiceSource
    -> FutureOneCInvoiceSource
    -> FutureCrmInvoiceSource

ReportExporter
    -> ExcelReportExporter
```

Использовать `typing.Protocol`, а не обязательное наследование от ABC, если нет отдельной причины для ABC.

Не создавать слишком общий интерфейс типа:

```python
class DataSource(Protocol):
    def load(self) -> list[object]: ...
```

Бизнес-контракт должен оставаться конкретным и типизированным.

---

## 8. DI и composition root

Конкретные adapters должны подставляться через dependency injection.

Не использовать отдельный тяжёлый DI framework.

FastAPI `Depends` можно использовать на API/composition уровне.

Composition root размещать, например, в:

```text
app/bootstrap/dependencies.py
```

Запрещено протаскивать FastAPI-зависимости внутрь domain/application core.

Плохо:

```python
# domain/service.py
service = Depends(...)
```

Хорошо:

```text
FastAPI route
   -> dependency factory
      -> ReconciliationService
         -> MatchingEngine
            -> matching rules
```

---

## 9. Domain model

Минимальные доменные сущности:

```text
Invoice
Payment
Allocation
UnallocatedAmount / UnallocatedPaymentPart
ReconciliationResult
MatchResult
```

### Invoice

Пример:

```python
@dataclass(frozen=True)
class Invoice:
    number: str
    date: date
    customer_name: str
    customer_inn: str
    amount: Decimal
```

### Payment

Пример:

```python
@dataclass(frozen=True)
class Payment:
    id: str
    document_number: str
    date: date
    payer_name: str
    payer_inn: str | None
    amount: Decimal
    purpose: str
```

### Allocation

`Payment` и `Invoice` имеют many-to-many relationship.

Нельзя моделировать это через одно поле `payment.invoice_id`.

Использовать отдельную сущность:

```python
@dataclass(frozen=True)
class Allocation:
    payment_id: str
    invoice_number: str
    amount: Decimal
    reason: "MatchReason"
```

Это обязательно, потому что в исходных данных есть:

- несколько платежей на один invoice;
- один payment на несколько invoices.

---

## 10. Деньги

Для любых денежных вычислений использовать только `Decimal`.

Запрещено использовать `float` для:

- invoice amount;
- payment amount;
- allocations;
- balances;
- totals.

Все значения должны быть нормализованы до копеек.

---

## 11. Где разрешён pandas/openpyxl

`pandas` и `openpyxl` должны оставаться на границе системы.

Правильно:

```text
CSV/XLSX
   -> adapter
      -> pandas/openpyxl
         -> list[Payment] / list[Invoice]
            -> domain/application
```

Неправильно:

```python
def reconcile(
    payments: pd.DataFrame,
    invoices: pd.DataFrame,
) -> pd.DataFrame:
    ...
```

Domain и application layer не должны зависеть от DataFrame.

---

## 12. Parsing и normalization

### Банковская выписка CSV

Нужно учитывать:

- кодировка `cp1251`;
- разделитель `;`;
- банковские метаданные до основной таблицы;
- итоговые строки после основной таблицы;
- пробелы / неразрывные пробелы в числах;
- десятичную запятую;
- поступления и списания;
- пустые значения;
- банковские контрольные итоги;
- возможные дубли строк.

Нельзя считать файл обычным CSV с заголовком в первой строке.

### XLSX реестр счетов

Нужно учитывать:

- таблица начинается не обязательно с первой строки;
- строку `Итого` нельзя считать invoice;
- invoice number может быть числом или строкой;
- amount может быть числом или строкой вида `66 909,55`;
- date может быть Excel date или строкой;
- ИНН всегда трактуется как строковый идентификатор.

Normalization выполняется в adapter layer до передачи данных в domain.

---

## 13. Matching engine

Matching должен быть детерминированным и объяснимым.

Не писать один огромный метод с большим количеством `if/elif`.

Использовать небольшие независимые правила:

```text
ExplicitInvoiceRule
MultipleInvoicesRule
InnAmountRule
```

Общий контракт может выглядеть так:

```python
class MatchingRule(Protocol):
    def match(
        self,
        payment: Payment,
        invoices: Sequence[Invoice],
        context: "MatchingContext",
    ) -> "MatchResult | None": ...
```

MatchingEngine получает ordered list правил.

Приоритет правил должен быть явным:

```text
1. explicit invoice reference
2. multiple explicit invoice references
3. unique INN + exact amount
4. no automatic match
```

Если ни одно безопасное правило не сработало — payment остаётся unallocated.

---

## 14. Запрет на fuzzy matching в MVP

Не использовать:

- fuzzy matching по названию компании;
- LLM matching;
- probabilistic confidence;
- embedding similarity;
- автоматический выбор среди нескольких кандидатов.

Для финансовой сверки лучше оставить платёж нераспределённым, чем неверно распределить деньги.

Архитектура может позволять в будущем добавить:

```text
ContractNumberRule
CounterpartySimilarityRule
MLMatchingRule
```

Но сейчас они не нужны.

---

## 15. Explainability

Каждое автоматическое решение должно иметь причину.

Примеры `match_type` / `reason`:

```text
invoice_number
multiple_invoice_numbers
inn_amount
third_party_with_invoice_reference
ambiguous
invoice_not_found
duplicate
overpayment
```

Нельзя просто возвращать `matched=True` без причины.

Результат должен быть пригоден для аудита человеком.

---

## 16. Специальные бизнес-кейсы исходного тестового набора

Эти кейсы обязательно должны быть покрыты кодом и тестами.

### 16.1 Несколько платежей на один invoice

Invoice `155` оплачивается двумя платежами:

```text
84 141,32
56 094,98
= 140 236,30
```

Invoice должен стать fully paid.

### 16.2 Один payment на несколько invoices

Один payment закрывает invoices:

```text
160
161
162
```

Суммы:

```text
44 048,55
85 703,85
36 631,90
= 166 384,30
```

Нужно создать несколько Allocation.

### 16.3 Partial payment

Invoice `165`:

```text
invoice:     157 085,10
paid:        156 935,10
outstanding:     150,00
```

Invoice `166`:

```text
outstanding: 5 000,00
```

### 16.4 Overpayment

Invoice `174`:

```text
invoice:      415 896,35
payment:      418 896,35
allocated:    415 896,35
unallocated:    3 000,00
```

Нельзя делать `allocated > invoice.amount`.

### 16.5 Third-party payment

Invoice `172` оплачивается другим лицом.

ИНН плательщика отличается от ИНН клиента, но назначение явно указывает invoice `172`.

Explicit invoice reference имеет приоритет, но результат должен содержать warning/reason о mismatch плательщика.

### 16.6 Payment without invoice number

Для invoice `168` номер счёта отсутствует в назначении, но комбинация:

```text
payer INN + exact amount
```

даёт ровно одного кандидата.

Разрешено автоматически сопоставить с `match_type=inn_amount`.

### 16.7 Ambiguous payment

Invoices `170` и `171` имеют одинаковые:

- customer;
- INN;
- date;
- amount.

Payment не содержит invoice number.

Нельзя выбирать один invoice автоматически.

Результат должен быть:

```text
ambiguous
candidates = [170, 171]
```

Весь payment остаётся unallocated.

### 16.8 Missing invoice

Есть payment со ссылкой на invoice `191`, которого нет в реестре.

Он должен остаться unallocated с соответствующей причиной.

### 16.9 Non-invoice income

Возврат налога не должен автоматически матчиться на invoice.

Он остаётся unallocated.

---

## 17. Duplicate detection

Это критический кейс.

В банковской выписке invoice `176` представлен одной и той же банковской операцией дважды.

Обе строки имеют один document number (`412`) и одинаковые данные.

Это duplicate одной банковской операции и учитывать её дважды нельзя.

Но invoice `177` содержит два настоящих одинаковых платежа с разными document numbers (`413` и `414`).

Их нельзя дедуплицировать.

Следовательно запрещено deduplicate только по:

```text
payer + amount + purpose
```

Identity банковской операции должен учитывать устойчивый business key / source identity, включая document number и другие необходимые поля.

Duplicate должен быть обнаружен и показан как warning, но не должен попадать в total income второй раз.

---

## 18. Извлечение invoice numbers из назначения

Нужно поддержать реальные варианты исходного набора, например:

```text
счет №142
сч. 145
счет 150
СЧЕТУ 151
inv-149
сч. 160, 161, 162
```

Необходимо покрыть regex/parser unit-тестами.

Не пытаться матчить расходные банковские операции как клиентские поступления.

---

## 19. Reconciliation invariants

Финансовые инварианты обязательны и должны проверяться кодом и тестами.

### 19.1 Общий баланс поступлений

```text
total_income = total_allocated + total_unallocated
```

Равенство должно выполняться до копейки.

### 19.2 Банковский баланс

Если выписка содержит контрольные суммы:

```text
opening_balance + income - expenses = closing_balance
```

Если формула не сходится, импорт должен содержать явный warning/error.

### 19.3 Invoice allocation

Для каждого invoice:

```text
0 <= allocated <= invoice_amount
```

### 19.4 Payment conservation

Для каждого payment:

```text
payment_amount = sum(payment_allocations) + unallocated_part
```

Никакие деньги не должны исчезать или появляться.

---

## 20. Контрольные значения для предоставленных файлов

Эти значения являются integration-test oracle для конкретного тестового набора.

```text
invoice count:                 41
invoice total:          7 781 624,50
bank income:            6 346 449,00
fully paid invoices:              32
partially paid invoices:           2
unpaid invoices:                   7
allocated:              5 906 786,10
unallocated:              439 662,90
outstanding invoices:    1 874 838,40
```

Главный invariant:

```text
5 906 786,10 + 439 662,90 = 6 346 449,00
```

### Partial invoices

```text
165 -> outstanding 150,00
166 -> outstanding 5 000,00
```

### Unpaid invoices

```text
14
146
153
170
171
178
179
```

### Unallocated total breakdown

```text
ambiguous 170/171            270 411,10
second real payment for 177   66 177,60
missing invoice 191           63 429,30
non-invoice tax refund        36 644,90
overpayment for 174            3 000,00
----------------------------------------
total                         439 662,90
```

Duplicate payment for invoice `176` не входит в unallocated total: это дубль строки source file, а не отдельное реальное поступление.

---

## 21. Application layer

Application service должен оркестрировать процесс, но не содержать file parsing или HTTP details.

Предпочтительно:

```python
class ReconciliationService:
    def __init__(
        self,
        matcher: MatchingEngine,
        validator: ReconciliationValidator,
    ) -> None:
        ...

    def execute(
        self,
        payments: PaymentBatch,
        invoices: InvoiceBatch,
    ) -> ReconciliationResult:
        ...
```

Поток:

```text
source adapters
   -> normalized domain input
      -> application service
         -> matching engine
            -> allocations / unallocated
               -> validation
                  -> ReconciliationResult
```

---

## 22. FastAPI/UI

UI должен быть простым и server-side.

Не создавать отдельный SPA.

Минимальный экран:

```text
Bank statement: [choose file]
Invoice registry: [choose file]

[Run reconciliation]
```

После обработки показать:

```text
Fully paid
Partially paid
Unpaid

Total income
Allocated
Unallocated

Balance check status
```

И кнопку:

```text
Download Excel report
```

Допускается Jinja2 + небольшой vanilla JS / HTMX, если это реально упрощает UX.

---

## 23. API routes

Минимально:

```text
GET  /
POST /reconcile
GET  /health
```

Дополнительный endpoint для download report допустим, если удобнее по реализации.

Не проектировать большой REST API без необходимости.

---

## 24. Persistence

PostgreSQL в текущем MVP не нужен.

Не добавлять:

```text
SQLAlchemy
Alembic
PostgreSQL
```

только ради демонстрации архитектуры.

Но domain/application должны позволять позже добавить persistence без переписывания core.

В README указать, что следующим production-шагом для платформы могут быть:

```text
ReconciliationRunRepository
history of runs
audit trail
manual resolutions
```

---

## 25. Масштабирование

Главный акцент текущего решения — functional extensibility, а не high-load ради high-load.

Архитектура должна позволять без переписывания core добавить:

```text
new bank CSV format
bank API
1C
CRM
Google Sheets
new matching rule
new report exporter
```

Приложение желательно держать stateless.

Если reconciliation станет тяжёлым, в будущем должно быть возможно заменить синхронный вызов:

```text
FastAPI -> ReconciliationService
```

на:

```text
FastAPI -> queue -> worker -> ReconciliationService
```

без переноса бизнес-логики из HTTP handlers.

Очередь сейчас реализовывать не нужно.

---

## 26. Excel report

Минимально сформировать листы:

```text
Summary
Invoices
Unallocated
Payments
```

### Invoices

Рекомендуемые поля:

```text
invoice_number
date
customer
inn
invoice_amount
allocated_amount
outstanding_amount
status
```

### Unallocated

Рекомендуемые поля:

```text
date
document_number
payer
inn
amount
purpose
reason
candidate_invoices
```

### Payments

Полезно показать allocations и reason/match_type для аудита.

Экспорт должен быть читаемым человеком, а не просто `DataFrame.to_excel()` без структуры.

---

## 27. Testing strategy

Тесты являются обязательной частью решения.

### Unit tests

Покрыть как минимум:

- money parsing;
- date parsing;
- invoice number normalization;
- invoice number extraction from purpose;
- multiple invoice references;
- exact invoice matching;
- multiple payments -> one invoice;
- one payment -> multiple invoices;
- partial payment;
- overpayment;
- third-party payment;
- unique `INN + exact amount`;
- ambiguous match;
- missing invoice;
- non-invoice payment;
- exact duplicate detection;
- two similar but real payments;
- financial invariants.

### Integration test

Обязательно должен существовать тест на исходных предоставленных CSV + XLSX, который проверяет контрольные значения из раздела 20.

Не проверять только HTTP status code — проверять бизнес-результат.

---

## 28. Code quality rules

Общие требования:

- использовать type hints;
- избегать `Any`, если тип можно выразить нормально;
- небольшие функции с одной ответственностью;
- не делать огромные service classes;
- не делать огромные regex без тестов;
- business logic не должна жить в route handlers;
- parsing не должен жить в domain;
- exporter не должен менять reconciliation result;
- side effects держать на границах системы;
- использовать descriptive names;
- не использовать сокращения без необходимости;
- comments нужны только там, где объясняют WHY, а не WHAT;
- не хардкодить конкретные invoice numbers или компании из тестовых данных в production code.

Не создавать абстракции заранее, если нет хотя бы понятной точки расширения.

Баланс:

> extensible, but not enterprise for enterprise's sake.

---

## 29. Error handling

Пользователь должен получать понятные ошибки для:

- unsupported file format;
- broken CSV/XLSX;
- отсутствующей ожидаемой таблицы;
- некорректной суммы;
- некорректной даты;
- нарушения банковского balance invariant;
- внутренних reconciliation invariant violations.

Не отдавать пользователю raw traceback.

Внутренние ошибки должны быть логируемыми.

---

## 30. Logging

Добавить базовое структурированное/понятное logging поведение.

Минимум логировать:

```text
reconciliation started
files parsed
payment count
invoice count
duplicates found
allocated total
unallocated total
validation result
report generated
```

Не логировать чувствительные данные целиком без необходимости.

---

## 31. README

README должен содержать:

### Запуск

Основной путь:

```bash
make up
```

### Tests / quality

```bash
make test
make lint
make typecheck
make check
```

### Architecture

Коротко объяснить:

```text
FastAPI -> Application -> Domain
                ^
                |
             Ports
                ^
                |
             Adapters
```

### Какие допущения сделаны

Обязательно зафиксировать как минимум:

- explicit invoice reference имеет приоритет над payer INN;
- unique `INN + exact amount` допускает automatic match;
- ambiguous candidate никогда не выбирается автоматически;
- overpayment выделяется в unallocated remainder;
- exact duplicate source operation учитывается один раз;
- банковские контрольные totals используются как validation source.

### Где ИИ ошибался и как это было замечено

Не придумывать этот раздел задним числом.

Во время разработки записывать реальные ошибки агента.

Хороший ожидаемый пример:

> ИИ предложил дедуплицировать платежи по payer + amount + purpose. При проверке данных обнаружились документы 413 и 414: они совпадают по этим полям, но являются двумя разными банковскими операциями. Поэтому identity операции была расширена document number, а кейс закреплён отдельным тестом.

Использовать только реальные случаи, которые действительно произошли во время реализации.

### Что бы было сделано ещё за один день

Предпочтительные production improvements:

```text
manual resolution of ambiguous payments
persistent reconciliation history
audit log
saved runs
configurable matching policies
1C/CRM integrations
monitoring/alerts
authentication/RBAC
```

Не ограничиваться фразой `улучшил бы UI`.

---

## 32. Что НЕ делать

Запрещено:

1. Хардкодить номера счетов, компании или суммы из конкретного тестового набора в production logic.
2. Использовать `float` для денег.
3. Делать fuzzy matching, который может самовольно распределить деньги.
4. Считать duplicate `176` и два реальных платежа `177` одним и тем же случаем.
5. Делать reconciliation через один большой pandas script.
6. Протаскивать DataFrame в domain layer.
7. Писать business logic прямо в FastAPI route.
8. Добавлять Kafka/Redis/Postgres/Celery только ради демонстрации технологий.
9. Создавать отдельный React frontend.
10. Писать приложение только под август 2026.
11. Игнорировать банковские контрольные суммы.
12. Автоматически разрешать ambiguity `170/171`.

---

## 33. Definition of Done

Перед завершением задачи обязательно выполнить всё ниже.

### Functional

- приложение принимает предоставленные CSV + XLSX;
- reconciliation выполняется корректно;
- UI показывает summary;
- Excel report скачивается;
- duplicate корректно обнаруживается;
- ambiguous payment остаётся unallocated;
- partial / overpayment / multi-payment / multi-invoice cases работают.

### Validation

На исходном датасете должны выполняться контрольные значения раздела 20.

### Quality

```bash
make check
```

проходит успешно.

### Startup

Проект должен запускаться с нуля по README.

Проверить сценарий reviewer:

```bash
git clone ...
make up
```

После этого web UI должен быть доступен без ручной настройки Python environment.

### Final manual review

Перед сдачей:

1. Поднять приложение с чистого состояния.
2. Загрузить исходные два файла через UI.
3. Проверить контрольные суммы.
4. Скачать Excel report.
5. Открыть report и визуально проверить данные.
6. Запустить `make check`.
7. Проверить README.
8. Проверить отсутствие абсолютных путей.
9. Проверить отсутствие hardcode конкретного месяца.
10. Проверить реальные ошибки ИИ и внести их в README.

---

## 34. Порядок реализации

Не начинать с UI.

Рекомендуемый порядок:

```text
1. Inspect input files and lock expected results.
2. Domain entities.
3. Parsing + normalization adapters.
4. Duplicate detection.
5. Matching rules.
6. Allocation/reconciliation engine.
7. Financial invariant validator.
8. Unit tests.
9. Integration test on provided files.
10. FastAPI application layer.
11. Server-side UI.
12. Excel exporter.
13. Docker / Compose / Makefile.
14. README.
15. Final manual end-to-end validation.
```

Сначала правильный core, потом presentation.

---

## 35. Основной инженерный принцип проекта

При любых спорных решениях руководствоваться следующим:

> Финансовая система должна быть консервативной: лучше явно показать нераспределённый или неоднозначный платёж, чем автоматически принять потенциально неверное решение.

И одновременно:

> Интеграционные детали должны быть заменяемыми, а бизнес-логика reconciliation — независимой от конкретного банка, CSV/XLSX и web framework.
