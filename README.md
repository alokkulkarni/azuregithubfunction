# GitHub Pull Request Monitor Azure Function

This Azure Function monitors pull requests in specified GitHub repositories on a scheduled basis.

## Features

- Fetches pull request data from multiple GitHub repositories
- Runs on a 30-minute schedule (configurable)
- Logs pull request details including title, state, creator, and URL
- Uses environment variables for configuration

## Setup

1. Create a GitHub Personal Access Token:
   - Go to GitHub Settings > Developer Settings > Personal Access Tokens
   - Generate a new token with `repo` scope
   - Copy the token

2. Configure Environment Variables:
   - Copy `.env.example` to `.env`
   - Fill in the following variables:
     - `GITHUB_TOKEN`: Your GitHub Personal Access Token
     - `GITHUB_ORG`: Your GitHub organization name
     - `GITHUB_REPOS`: Comma-separated list of repository names to monitor

3. Install Dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Deploy to Azure:
   - Create a new Azure Function App
   - Deploy the function code
   - Configure the application settings with your environment variables

## Configuration

The function runs every 30 minutes by default. To change the schedule, modify the `schedule` value in `function.json` using cron expressions.

## Logging

The function logs the following information for each pull request:
- Pull request number and title
- Current state
- Creator's GitHub username
- Pull request URL

## Error Handling

The function includes error handling for:
- Missing environment variables
- GitHub API request failures
- Invalid repository names 