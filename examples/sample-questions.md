Category: BZ_Sample
Description: This sample set contains 10 SQL practice questions.
ImageMaxWidth: 500

## Primary key purpose
What is the primary purpose of a PRIMARY KEY in a relational table?

```sql
CREATE TABLE users (
  id INT PRIMARY KEY,
  email VARCHAR(255) NOT NULL
);
```

- [ ] Uniquely identify each row
- [x] Store large text values
- [ ] Improve query caching
- [ ] Control transaction isolation

## INNER JOIN effect (with code answers)
What does an INNER JOIN return?

```sql
SELECT c.id, o.total
FROM customers c
INNER JOIN orders o ON c.id = o.customer_id;
```

- [x] Rows where the join condition matches in both tables
- [ ] All rows from the left table only
  ```sql
  SELECT c.id, o.total
  FROM customers c
  LEFT JOIN orders o ON c.id = o.customer_id;
  ```
- [ ] All rows from both tables regardless of condition
- [ ] Only unmatched rows from the right table

## LEFT JOIN behavior (with code answers)
In a LEFT JOIN, what happens to rows in the left table with no match in the right table?

```sql
SELECT c.id, o.total
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id;
```

- [x] They are returned with NULLs for right table columns
- [ ] They are excluded from the result
- [ ] They duplicate right table rows
  ```sql
  SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.id IS NULL;
  ```
- [ ] They cause a join error

## GROUP BY requirement (with code answers)
When using GROUP BY, which columns must appear in the GROUP BY list?

```sql
SELECT department, COUNT(*) AS headcount
FROM employees
GROUP BY department;
```

- [x] All non-aggregated columns selected
- [ ] Only primary key columns
- [ ] Only numeric columns
  ```sql
  SELECT department, COUNT(*) FROM employees GROUP BY salary;
  ```
- [ ] No columns; GROUP BY is optional

## HAVING clause (with code answers)
What is the HAVING clause used for?

```sql
SELECT department, COUNT(*) AS headcount
FROM employees
GROUP BY department
HAVING COUNT(*) > 5;
```

- [x] Filtering groups after aggregation
- [ ] Filtering rows before aggregation
- [ ] Declaring table aliases
  ```sql
  SELECT d AS dept FROM employees;
  ```
- [ ] Specifying join conditions

## NULL comparisons
How do you test for NULL in SQL?

```sql
SELECT *
FROM users
WHERE email IS NULL;
```

- [x] Use IS NULL / IS NOT NULL
- [ ] Use = NULL / != NULL
- [ ] Use == NULL
- [ ] Use NULL ?

## Transaction isolation (with code answers)
Which isolation level prevents dirty reads but allows non-repeatable reads?

```java
Connection conn = dataSource.getConnection();
conn.setTransactionIsolation(Connection.TRANSACTION_READ_COMMITTED);
```

- [ ] READ UNCOMMITTED
  ```java
  conn.setTransactionIsolation(Connection.TRANSACTION_READ_UNCOMMITTED);
  ```
- [x] READ COMMITTED
- [ ] REPEATABLE READ
- [ ] SERIALIZABLE

## Index choice
Which column is typically best suited for an index?

```sql
CREATE INDEX idx_users_email ON users(email);
```

- [x] High-selectivity columns used in WHERE filters
- [ ] Columns with very few distinct values
- [ ] 
  ```sql
  CREATE INDEX idx_unused ON logs(debug_flag);
  ```
- [ ] Large BLOB columns

## Normalization goal
What is a primary goal of database normalization?

```sql
-- Split repeating customer and order data into separate tables
CREATE TABLE customers (id INT PRIMARY KEY, name TEXT);
CREATE TABLE orders (id INT PRIMARY KEY, customer_id INT REFERENCES customers(id), total NUMERIC);
```

- [x] Reduce redundancy and update anomalies
- [ ] Maximize denormalization for speed
- [ ] Require every table to have a composite key
- [ ] Force all columns to be VARCHAR

## Fill-in-the-blank keyword
Type: Cloze
Fill in the missing Java keyword.

The method should {{return}} its value.

```java
public int add(int a, int b) {
    {{int}} sum = a + b;
    {{return}} sum;
}
```

## New MCQ

```sql
-- Split repeating customer and order data into separate tables
CREATE TABLE customers (id INT PRIMARY KEY, name TEXT);
CREATE TABLE orders (id INT PRIMARY KEY, customer_id INT REFERENCES customers(id), total NUMERIC);
```

- [x] Correct answer
- [ ] Incorrect answer

## Description
Type: Description
Type your description here.

## New MCQ
Question text here.
- [x] Correct answer
- [ ] Incorrect answer

## Fill in the blank
Type: Cloze
Complete the sentence: {{answer}} goes here.
