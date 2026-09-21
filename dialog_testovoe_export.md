# Экспорт диалога: тестовое задание по сверке платежей

---

## Пользователь

давай тогда уже спроектируем и выполним тестовое так, чтобы потом можно было нормально делегировать агенту. в качестве стэка: FastAPI, фронтенд на твое усмотрение. модульный монолит, интерфейсы/Protocol для источников данных, DI для конкретных адаптеров, Docker Compose для запуска, Makefile с понятными командами и uv как пакетный менеджер сейчас у нас csv банка и эксель со счетами, но дальше могут появиться 1с, срмки, или другой формат поэтому core не должен зависеть от конкретного файла Ещё важно заранее учесть что Decimal для денег. надо также проанализировать другие подводные камни

## ChatGPT

Да, это хорошее направление. Тогда я бы строил решение именно вокруг твоей идеи: **не одноразовый скрипт, а небольшой расширяемый application core**, где CSV/XLSX — только текущие адаптеры, а бизнес-логика сверки от них не зависит.

Сначала зафиксируем план работ, контрольные суммы и все edge cases, чтобы агент не принимал бизнес-решения на ходу. После этого отдельно разложим предложенную тобой архитектуру по слоям, DI/портам/адаптерам и уже потом закрепим code style и правила реализации.

### План выполнения тестового

#### Этап 0. Зафиксировать эталонный результат

Для предоставленных файлов ожидаем:

| Метрика | Значение |
|---|---:|
| Счетов | 41 |
| Сумма счетов | 7 781 624,50 ₽ |
| Поступления по банковскому итогу | 6 346 449,00 ₽ |
| Полностью оплачено счетов | 32 |
| Частично оплачено | 2 |
| Не оплачено | 7 |
| Распределено | 5 906 786,10 ₽ |
| Нераспределено | 439 662,90 ₽ |
| Остаток задолженности | 1 874 838,40 ₽ |

Ключевая проверка:

```text
5 906 786,10 + 439 662,90 = 6 346 449,00
```

Это будет integration-test oracle.

#### Этап 1. Разобрать входные файлы

**Банковская CSV:**
- `cp1251`, не UTF-8;
- разделитель `;`;
- неразрывные пробелы в числах;
- десятичная запятая;
- метаданные перед таблицей;
- итоги после таблицы;
- поступления и списания;
- пустые значения;
- официальный итог по поступлениям как контроль;
- продублированная строка.

**Реестр XLSX:**
- таблица не с первой строки;
- есть строка `Итого`;
- номер счёта местами `int`, местами `str`;
- сумма местами число, местами строка вроде `"66 909,55"`;
- дата местами Excel date, а у счёта `171` строка `"16.08.2026"`;
- ИНН трактуем как строковый идентификатор.

#### Этап 2. Нормализация

Нормализовать:

```text
invoice_number
document_number
date
inn
amount
counterparty
payment_purpose
```

Деньги — только `Decimal`, не `float`.

#### Этап 3. Валидировать банковскую выписку до matching

В CSV два раза идентичная операция:

```text
document = 412
amount = 32 262,30
invoice = 176
```

Сумма всех строк даёт `6 378 711,30 ₽`, официальный банковский оборот — `6 346 449,00 ₽`, разница — `32 262,30 ₽`. Значит, duplicate должен быть обнаружен.

Нельзя дедуплицировать просто по `payer + amount + purpose`, потому что по счёту `177` есть два настоящих одинаковых платежа с разными документами `413` и `414`.

```text
412 + 412 → duplicate
413 + 414 → две реальные операции
```

#### Этап 4. Извлечение ссылок на счета

Поддержать формы:

```text
счет №142
сч. 145
счет 150
СЧЕТУ 151
inv-149
сч. 160, 161, 162
```

Matching применять к релевантным поступлениям.

#### Этап 5. Reconciliation

Поддержать:
- обычный `payment → invoice`;
- несколько платежей на один счёт (`155`);
- один платёж на несколько счетов (`160 + 161 + 162`);
- частичную оплату (`165`, `166`);
- переплату (`174`);
- оплату третьим лицом (`172`);
- платёж без номера счёта, но с уникальным `ИНН + сумма` (`168`);
- неоднозначный платёж (`170` и `171`) — не угадывать, оставить `AMBIGUOUS`.

#### Этап 6. Хранить причину каждого решения

Например:

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

Не использовать непрозрачные confidence-score вроде `0.873`.

#### Этап 7. Статусы счетов

Для invoice хранить:

```text
invoice_amount
allocated_amount
outstanding_amount
status
```

Статусы: `paid`, `partial`, `unpaid`.

Неоплаченные: `14, 146, 153, 170, 171, 178, 179`.
Частичные: `165, 166`.

#### Этап 8. Нераспределённые деньги

| Причина | Сумма |
|---|---:|
| ambiguous 170/171 | 270 411,10 |
| второй платёж 177 | 66 177,60 |
| неизвестный счёт 191 | 63 429,30 |
| возврат налога | 36 644,90 |
| переплата 174 | 3 000,00 |
| **Итого** | **439 662,90** |

Duplicate `176` сюда не входит.

#### Этап 9. Финансовые инварианты

```text
total_income = allocated + unallocated
```

```text
opening_balance + income - expenses = closing_balance
```

Для каждого счёта:

```text
0 <= allocated <= invoice_amount
```

Для каждого платежа:

```text
payment_amount = sum(allocations) + unallocated_part
```

#### Этап 10. Excel-отчёт

Минимум листы:

```text
Сводка
Счета
Нераспределенные
Поступления
```

#### Этап 11. Минимальный UI

Два файла → кнопка «Провести сверку» → сводка → «Скачать Excel».

Без React/SPA.

#### Этап 12. Тесты

Unit-тесты на:
- деньги;
- даты;
- invoice-number extraction;
- несколько invoice numbers;
- partial;
- many payments → one invoice;
- one payment → many invoices;
- overpayment;
- third-party;
- unique `INN + amount`;
- ambiguous;
- missing invoice;
- exact duplicate;
- два похожих, но реальных платежа;
- reconciliation invariant.

Плюс end-to-end test на предоставленных CSV/XLSX.

#### Этап 13. README

Обязательные разделы:
- допущения;
- где ИИ ошибался и как это заметили;
- что бы доделали ещё за день.

Пример реальной ошибки ИИ для фиксации:

> ИИ предложил deduplicate по amount + payer + purpose. Я проверил данные и обнаружил документы 413 и 414: они одинаковы по этим признакам, но являются двумя разными банковскими операциями. Поэтому добавил document_number в identity операции и тест.

#### Этап 14. Финальная проверка

1. Поднять проект с нуля по README.
2. Загрузить два файла через UI.
3. Сверить контрольные цифры.
4. Скачать и открыть Excel.
5. Проверить неправильные файлы.
6. Запустить тесты.
7. Проверить отсутствие absolute paths и хардкода августа 2026.
8. Убедиться, что решение работает на новых месячных файлах.
9. Привести README в состояние для reviewer.

Главные ловушки:
1. Не хардкодить август и номера счетов.
2. Не использовать `float` для денег.
3. Не делать fuzzy matching, который самовольно распределяет деньги.
4. Не путать duplicate 176 и два реальных платежа 177.
5. Не делать один огромный pandas-скрипт.

Порядок за 4–6 часов:
- 1–1.5 ч: импорт + нормализация + модели;
- 1.5–2 ч: reconciliation + edge cases;
- ~1 ч: тесты;
- ~45 мин: UI + Excel;
- ~45 мин: README + Docker + финальная проверка.

---

## Пользователь

Так хорошо, давай обсудим архитектуру

Мы будем делать акцент на масштбаирование, щас нам просто дана выписка из банка тупо но могут быть и другие форматы потому в коде я бы использовал интерфейсы а di уже посдавля конкретную реализацию нужного нам интегроованного сервиса, в коде хочу иметь мейк файл чтобы запускать не через непривычные человеку команды а читаемые, запускать сервис также через makefile - команда просто будет докеркомпоуз вызывать

## ChatGPT

Да, направление правильное. Акцент лучше сделать не на масштабировании по нагрузке ради тестового, а на **расширяемости архитектуры**: сегодня CSV банка + XLSX счетов, завтра 1С API + CRM + другой банк + Google Sheets.

Для тестового — **модульный монолит на FastAPI с лёгкой hexagonal/clean архитектурой**, без Kafka/Celery/Postgres ради красоты.

### Общая схема

```text
                    ┌─────────────────┐
                    │   Web / FastAPI │
                    │ Jinja2 / HTMX   │
                    └────────┬────────┘
                             │
                     Application layer
                             │
                 ReconciliationUseCase
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   PaymentSource       InvoiceSource       ReportExporter
       Port                Port                Port
          │                  │                  │
     adapters/          adapters/          adapters/
          │                  │                  │
     Bank CSV          XLSX Registry        XLSX Report
     Future API        Future 1C/CRM        Future ...
          │                  │
          └──────────────┬───┘
                         ▼
                       Domain
                  ReconciliationEngine
                  Matching policies
                  Allocations
                  Invariants
```

Главный принцип: **домен не знает о CSV, Excel, FastAPI, Docker и pandas**. Он получает нормализованные `Payment` и `Invoice`.

### Порты

Не привязываться к `CsvParser`, а использовать более предметные контракты:

```python
class PaymentSource(Protocol):
    def load(self, source: Source) -> PaymentBatch: ...

class InvoiceSource(Protocol):
    def load(self, source: Source) -> InvoiceBatch: ...
```

Сегодня:

```text
BankCsvPaymentSource
ExcelInvoiceSource
```

Позже:

```text
TBankApiPaymentSource
SberApiPaymentSource
OneCPaymentSource
CrmPaymentSource
OneCInvoiceSource
CrmInvoiceSource
GoogleSheetsInvoiceSource
```

Не делать один универсальный `DataSource[Any]`; оставить отдельные порты `PaymentSource`, `InvoiceSource`, `ReportExporter`.

### Domain

Основные сущности:

```text
Invoice
Payment
Allocation
UnallocatedAmount
MatchCandidate
ReconciliationResult
```

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

`Allocation` — отдельная сущность, потому что связь `Payment ↔ Invoice` many-to-many:

```python
@dataclass(frozen=True)
class Allocation:
    payment_id: str
    invoice_number: str
    amount: Decimal
    reason: MatchReason
```

### Matching как набор правил

Не один большой `if/elif`, а цепочка политик:

```text
ExplicitInvoiceRule
MultipleInvoicesRule
InnAmountRule
```

Контракт:

```python
class MatchingRule(Protocol):
    def match(
        self,
        payment: Payment,
        invoices: Sequence[Invoice],
        context: MatchingContext,
    ) -> MatchResult | None:
        ...
```

Приоритет правил задаётся явно:

```python
rules = [
    ExplicitInvoiceRule(),
    MultipleInvoicesRule(),
    InnAmountRule(),
]
```

Fuzzy matching сейчас не реализовывать. Лучше `UNKNOWN`, чем ошибочный автоматический match.

### Application layer

Use case лучше строить так, чтобы зависимости приходили через constructor:

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

### DI

Без отдельного тяжёлого DI framework. FastAPI `Depends` — только в presentation/composition слое.

```python
def get_matching_engine() -> MatchingEngine:
    return MatchingEngine(
        rules=[
            ExplicitInvoiceRule(),
            MultipleInvoicesRule(),
            InnAmountRule(),
        ],
    )
```

Composition root можно вынести в:

```text
app/bootstrap/dependencies.py
```

### Структура проекта

```text
.
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── routes/
│   │   │   ├── reconciliation.py
│   │   │   └── health.py
│   │   └── schemas/
│   ├── application/
│   │   ├── services/
│   │   │   └── reconciliation.py
│   │   └── dto/
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── invoice.py
│   │   │   ├── payment.py
│   │   │   └── allocation.py
│   │   ├── matching/
│   │   │   ├── engine.py
│   │   │   └── rules/
│   │   │       ├── explicit_invoice.py
│   │   │       ├── multiple_invoices.py
│   │   │       └── inn_amount.py
│   │   └── reconciliation/
│   │       ├── result.py
│   │       └── validator.py
│   ├── ports/
│   │   ├── payment_source.py
│   │   ├── invoice_source.py
│   │   └── report_exporter.py
│   ├── adapters/
│   │   ├── payment_sources/
│   │   │   └── bank_csv.py
│   │   ├── invoice_sources/
│   │   │   └── excel.py
│   │   └── reports/
│   │       └── excel.py
│   ├── bootstrap/
│   │   └── dependencies.py
│   ├── templates/
│   └── static/
├── tests/
│   ├── unit/
│   └── integration/
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── README.md
└── .env.example
```

### Frontend

FastAPI + Jinja2 + немного vanilla JS или HTMX. Отдельный React/Node frontend не нужен.

### БД

PostgreSQL в MVP не нужен, если нет требования хранить историю. Архитектуру оставить готовой к появлению `ReconciliationRunRepository`, `PaymentRepository`, `InvoiceRepository` позже.

### Масштабирование

Функциональное масштабирование — через ports/adapters и DI.

Масштабирование нагрузки позже возможно через stateless FastAPI + worker queue, потому что `ReconciliationService` не зависит от HTTP.

### Docker Compose

Даже если сервис один:

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
```

### Makefile

Команды:

```bash
make build
make up
make down
make restart
make logs
make test
make lint
make format
make check
```

### Quality tooling

```text
ruff
mypy
pytest
```

### Protocol или ABC

Для портов — `typing.Protocol`.

### Где использовать pandas

Только на границе системы:

```text
CSV → pandas → list[Payment] → DOMAIN
```

Не протаскивать `DataFrame` в домен.

### Итоговые архитектурные решения

1. Modular monolith.
2. FastAPI + server-side frontend.
3. Hexagonal architecture light.
4. Порты через `Protocol`.
5. Конкретные adapters подключаются через DI/composition root.
6. `pandas/openpyxl` только в adapters.
7. Matching — независимые rules/policies.
8. Payment ↔ Invoice через `Allocation`.
9. Деньги — `Decimal`.
10. Stateless приложение; Postgres/queue сейчас не нужны.
11. Docker Compose.
12. Makefile.
13. `pytest + ruff + mypy`.
14. Архитектура допускает Postgres, worker queue, API/1C adapters без переписывания core.

---

## Пользователь

Еще uv в качестве пакетного менеджера, и .toml файл, чтобы по мере роста проекта, можно было локально правильно работаь с зависимостями и давай офрмим .md файл который я добавлю в репо для агента

## Пользователь

Продолжай

## ChatGPT

Соберу это именно как `AGENTS.md`, чтобы агент воспринимал файл как рабочую спецификацию репозитория. Добавлю `uv`, зафиксированную архитектуру, контрольные результаты, безопасные правила matching, границы слоёв, Makefile/Docker и ограничения против overengineering.

## ChatGPT

Готово. Я оформил всё в `AGENTS.md`: архитектуру, `uv`, Docker Compose, Makefile, DI/ports/adapters, matching rules, контрольные суммы, edge cases, тестовую стратегию, Definition of Done и ограничения против overengineering.

Его уже можно класть в корень репозитория и отдавать агенту как основную спецификацию.

---

