# Kafka Jira Worklogs CSV Columns

This document describes the columns in the `kafka_worklogs.csv` file generated by the Kafka Jira worklog collection script.

| Column              | Description                                      |
|---------------------|--------------------------------------------------|
| issue_key           | Jira issue key (e.g., KAFKA-12345)               |
| worklog_id          | Internal worklog entry ID                         |
| author              | Display name of the person who logged the work    |
| time_spent_seconds  | Time spent in seconds                             |
| time_spent          | Time spent in human-readable format (e.g., "2h") |
| started             | When the work was started (ISO format)           |
| created             | When the worklog entry was created (ISO format)  |
| updated             | When the worklog entry was last updated          |
| comment             | Worklog comment/description                       | 