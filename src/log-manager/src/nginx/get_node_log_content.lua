-- Copyright (c) Microsoft Corporation
-- All rights reserved.
-- MIT License
-- Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
-- documentation files (the "Software"), to deal in the Software without restriction, including without limitation
-- the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
-- to permit persons to whom the Software is furnished to do so, subject to the following conditions:
-- The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
-- THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
-- BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
-- NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
-- DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

--[[
Node Log Content API with Time Filtering
 - GET /api/v1/node-logs/{filename} - Get system log content
=======================================

This API endpoint allows fetching system logs with time-based filtering.
It supports extracting timestamps from various log formats using either 
built-in format detection or custom regex patterns.

Query Parameters:
----------------
- token: Authentication token
- node: Node name/ID
- tail-mode: If "true", return the last N lines of the log
- lines: Number of lines to return in tail mode (default: 10000)
- start: Start byte position (default: 0)
- end: End byte position (optional)

New Time Filtering Parameters:
----------------------------
- start-time: Filter logs after this time (format: "YYYY-MM-DD HH:MM:SS")
- end-time: Filter logs before this time (format: "YYYY-MM-DD HH:MM:SS")
- timestamp-regex: Custom regex to extract timestamps from log lines

Custom Timestamp Regex Format:
------------------
The timestamp-regex should use named capture groups to extract timestamp components.
Either provide all components:
  (?<year>\d{4})-(?<month>\d{2})-(?<day>\d{2})T(?<hour>\d{2}):(?<min>\d{2}):(?<sec>\d{2})

Or a single timestamp capture:
  (?<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})

If no custom regex is provided, common timestamp formats are automatically detected.

Custom Log Regex:
------------------
- log-regex: Optional regex to filter log lines based on content
- If provided, only lines matching this regex will be included in the output.

Example Usage:
------------
/api/v1/node-logs/syslog?token=XXX&node=node1&start-time=2025-07-07 00:00:00&end-time=2025-07-07 12:00:00
/api/v1/node-logs/journal-kubelet.service?token=XXX&node=node1&start-time=2025-07-07 00:00:00&end-time=2025-07-07 12:00:00

]]--

local lfs = require "lfs"
local util = require "util"

-- Use the allowed_logs and is_allowed_log function from util.lua

local args = ngx.req.get_uri_args()
local token = args["token"]
local node_name = args["node"] 
local tail_mode = args["tail-mode"]
local lines = tonumber(args["lines"]) or 10000
local start_byte = tonumber(args["start"]) or 0
local end_byte = tonumber(args["end"])

-- New filtering parameters
local start_time = args["start-time"] -- Format: YYYY-MM-DD HH:MM:SS
local end_time = args["end-time"]     -- Format: YYYY-MM-DD HH:MM:SS
local timestamp_regex = args["timestamp-regex"] -- Regex pattern to extract timestamp from log lines
local log_regex = args["log-regex"] -- Optional regex to filter log lines

-- Extract log filename from URI
local log_filename = ngx.var[1]  -- Captured from regex in location block

if not token or not log_filename then
  ngx.log(ngx.ERR, "token and log filename are required")
  ngx.status = ngx.HTTP_BAD_REQUEST
  return ngx.exit(ngx.HTTP_OK)
end

-- Security check: only allow predefined log files
if not util.is_allowed_log(log_filename) then
  ngx.log(ngx.ERR, "access to log file not allowed: " .. log_filename)
  ngx.status = ngx.HTTP_FORBIDDEN
  return ngx.exit(ngx.HTTP_OK)
end

local log_path = ""

-- Check if this is a systemd journal log
local is_journal = util.is_journal_log(log_filename)

if is_journal then
  -- For journal logs, we'll use journalctl command with custom path instead of direct file access
  local journal_path = util.get_journal_path()
  local can_access = util.can_access_journal(journal_path)
  
  ngx.log(ngx.INFO, "Journal log requested, will use journalctl with path: " .. journal_path)
  ngx.log(ngx.INFO, "Journal path accessible: " .. tostring(can_access))
  
  -- Set appropriate headers
  ngx.header["Content-Type"] = "text/plain"
  ngx.header["X-Node-Name"] = node_name or "unknown"
  ngx.header["X-Log-File"] = "journal"
  ngx.header["X-Journal-Path"] = journal_path
  
  -- Handle journal logs with journalctl
  local journalctl_cmd = "journalctl"
  
  -- Only add directory option if we can access the journal there
  if can_access then
    journalctl_cmd = journalctl_cmd .. " --directory=" .. journal_path
  else
    ngx.log(ngx.WARN, "Cannot access journal at " .. journal_path .. ", using system default")
  end
  
  -- Add filtering parameters
  if start_time then
    journalctl_cmd = journalctl_cmd .. " --since=\"" .. start_time .. "\""
  end
  if end_time then
    journalctl_cmd = journalctl_cmd .. " --until=\"" .. end_time .. "\""
  end
  
  -- Add specific unit/service filtering if specified in the log filename
  local unit_match = string.match(log_filename, "^journal%-(.+)$")
  if unit_match then
    journalctl_cmd = journalctl_cmd .. " -u " .. unit_match
  end
  
  -- Add lines limit if in tail mode
  if tail_mode == "true" then
    journalctl_cmd = journalctl_cmd .. " -n " .. lines
  end
  
  -- Add output formatting - plain text with full timestamps
  journalctl_cmd = journalctl_cmd .. " -o short-full"
  
  -- Add fallback options in case journalctl fails
  journalctl_cmd = journalctl_cmd .. " 2>/dev/null || echo 'Failed to read journal logs from " .. journal_path .. "'"
  
  ngx.log(ngx.INFO, "Executing: " .. journalctl_cmd)
  
  -- Execute journalctl command
  local handle = io.popen(journalctl_cmd)
  if handle then
    local content = handle:read("*a")
    handle:close()
    
    if content == "" then
      content = "No journal entries found in " .. journal_path
    end
    
    -- Apply regex filtering if needed
    if log_regex or timestamp_regex then
      local filtered_lines = {}
      for line in content:gmatch("[^\r\n]+") do
        local keep_line = true
        
        if timestamp_regex then
          local matched = ngx.re.match(line, timestamp_regex, "jo")
          if not matched then
            keep_line = false
          end
        end
        
        if log_regex and keep_line then
          local matched = ngx.re.match(line, log_regex, "jo")
          if not matched then
            keep_line = false
          end
        end
        
        if keep_line then
          table.insert(filtered_lines, line)
        end
      end
      content = table.concat(filtered_lines, "\n")
    end
    
    ngx.say(content)
    return ngx.exit(ngx.HTTP_OK)
  else
    ngx.status = ngx.HTTP_INTERNAL_SERVER_ERROR
    ngx.say("Failed to execute journalctl command")
    return ngx.exit(ngx.HTTP_OK)
  end
else
    -- Regular log file handling
    log_path = "/usr/local/node/log/" .. log_filename
    
    local attr = lfs.attributes(log_path)
    
    if not attr or attr.mode ~= "file" then
        ngx.log(ngx.ERR, "log file not found: " .. log_path)
        ngx.status = ngx.HTTP_NOT_FOUND
        return ngx.exit(ngx.HTTP_OK)
    end

    -- Set response headers
    ngx.header["Content-Type"] = "text/plain"
    ngx.header["X-Node-Name"] = node_name or "unknown"
    ngx.header["X-Log-File"] = log_filename
    ngx.header["X-File-Size"] = attr.size

    -- Handle compressed files
    if string.match(log_filename, "%.gz$") then
    ngx.header["Content-Encoding"] = "gzip"
    end

    -- Helper function to convert timestamp string to Unix timestamp
    local function parse_timestamp(time_str)
        if not time_str then return nil end
        
        local pattern = "(%d+)-(%d+)-(%d+) (%d+):(%d+):(%d+)"
        local year, month, day, hour, min, sec = time_str:match(pattern)
        
        if not year then return nil end
        
        return os.time({
            year = tonumber(year),
            month = tonumber(month),
            day = tonumber(day),
            hour = tonumber(hour),
            min = tonumber(min),
            sec = tonumber(sec)
        })
    end

    -- Helper function to extract timestamp from log line using custom regex or built-in formats
    local function extract_timestamp(line, custom_regex)
        -- First try custom regex if provided
        if custom_regex then
            local captures = {}
            local matched = nil
            
            -- Try to use the regex with ngx.re.match
            local ok, result = pcall(function()
                return ngx.re.match(line, custom_regex, "jo")
            end)
            
            if ok and result then
                matched = result
                
                -- Check if the regex has named capture groups for timestamp components
                if matched["year"] and matched["month"] and matched["day"] and 
                matched["hour"] and matched["min"] and matched["sec"] then
                    return os.time({
                        year = tonumber(matched["year"]),
                        month = tonumber(matched["month"]),
                        day = tonumber(matched["day"]),
                        hour = tonumber(matched["hour"]),
                        min = tonumber(matched["min"]),
                        sec = tonumber(matched["sec"])
                    })
                -- If the regex has a named capture for a full ISO timestamp
                elseif matched["timestamp"] then
                    -- Try to parse the timestamp capture
                    local ts = matched["timestamp"]
                    local year, month, day, hour, min, sec = ts:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
                    if year then
                        return os.time({
                            year = tonumber(year),
                            month = tonumber(month),
                            day = tonumber(day),
                            hour = tonumber(hour),
                            min = tonumber(min),
                            sec = tonumber(sec)
                        })
                    end
                end
            end
        end
        
        -- Fall back to built-in formats
        
        -- Try ISO format: 2025-07-07T09:32:45
        local year, month, day, hour, min, sec = line:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
        
        if year then
            return os.time({
                year = tonumber(year),
                month = tonumber(month),
                day = tonumber(day),
                hour = tonumber(hour),
                min = tonumber(min),
                sec = tonumber(sec)
            })
        end
        
        -- Try syslog format: Jul  7 09:32:45
        local month_str, day, hour, min, sec = line:match("(%a+)%s+(%d+)%s+(%d+):(%d+):(%d+)")
        
        if month_str then
            local months = {Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12}
            local month_num = months[month_str]
            local current_year = os.date("%Y")
            
            if month_num then
                return os.time({
                    year = tonumber(current_year),
                    month = month_num,
                    day = tonumber(day),
                    hour = tonumber(hour),
                    min = tonumber(min),
                    sec = tonumber(sec)
                })
            end
        end
        
        -- Try another common format: 2025/07/07 09:32:45
        year, month, day, hour, min, sec = line:match("(%d+)/(%d+)/(%d+)%s+(%d+):(%d+):(%d+)")
        if year then
            return os.time({
                year = tonumber(year),
                month = tonumber(month),
                day = tonumber(day),
                hour = tonumber(hour),
                min = tonumber(min),
                sec = tonumber(sec)
            })
        end
        
        -- Try systemd journal format: Jul 07 09:32:45.123456
        month_str, day, hour, min, sec = line:match("(%a+)%s+(%d+)%s+(%d+):(%d+):(%d+)%.%d+")
        if month_str then
            local months = {Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12}
            local month_num = months[month_str]
            local current_year = os.date("%Y")
            
            if month_num then
                return os.time({
                    year = tonumber(current_year),
                    month = month_num,
                    day = tonumber(day),
                    hour = tonumber(hour),
                    min = tonumber(min),
                    sec = tonumber(sec)
                })
            end
        end
        
        return nil
    end

    -- Helper function to filter log content by timestamp and pattern
    local function filter_log_content(content, start_timestamp, end_timestamp, timestamp_regex, log_regex)
        if not content or content == "" then return "" end
        
        -- If no filters, return the original content
        if not start_timestamp and not end_timestamp then
            return content
        end
        
        local filtered_lines = {}
        
        -- Process line by line
        for line in content:gmatch("[^\r\n]+") do
            local keep_line = true
            
            -- Apply timestamp filter if needed
            if start_timestamp or end_timestamp then
                local line_timestamp = extract_timestamp(line, timestamp_regex)
                
                if line_timestamp then
                    if start_timestamp and line_timestamp < start_timestamp then
                        keep_line = false
                    end
                    
                    if end_timestamp and line_timestamp > end_timestamp then
                        keep_line = false
                    end
                else
                    -- If we couldn't extract a timestamp and filtering by time is requested,
                    -- don't include lines without timestamps
                    if start_timestamp or end_timestamp then
                        keep_line = false
                    end
                end
            end

            if log_regex then
                -- Apply log regex filter if provided
                local log_match = ngx.re.match(line, log_regex, "jo")
                if not log_match then
                    keep_line = false
                end
            end
            
            if keep_line then
                table.insert(filtered_lines, line)
            end
        end
        
        return table.concat(filtered_lines, "\n")
    end

    -- Parse timestamps if provided
    local start_timestamp = parse_timestamp(start_time)
    local end_timestamp = parse_timestamp(end_time)

    -- Handle different access modes
    if tail_mode == "true" then
        -- Tail mode: get last N lines
        local cmd = "tail -n " .. lines .. " '" .. log_path .. "'"
        local handle = io.popen(cmd)
        if handle then
            local content = handle:read("*a")
            handle:close()
            
            -- Apply filters (timestamp with custom regex if provided)
            local filtered_content = filter_log_content(content, start_timestamp, end_timestamp, timestamp_regex, log_regex)
            
            ngx.say(filtered_content)
            return ngx.exit(ngx.HTTP_OK)  -- Explicitly end request processing
        else
            ngx.status = ngx.HTTP_INTERNAL_SERVER_ERROR
            ngx.say("Failed to read log file")
            return ngx.exit(ngx.HTTP_OK)  -- Explicitly end request processing
        end
    else
        -- Normal mode: get content from start_byte to end_byte
        local file = io.open(log_path, "rb")
        if not file then
            ngx.status = ngx.HTTP_INTERNAL_SERVER_ERROR
            ngx.say("Failed to open log file")
            return ngx.exit(ngx.HTTP_OK)
        end
        
        -- Move to start byte
        file:seek("set", start_byte)
        
        local content = file:read(end_byte and (end_byte - start_byte) or "*a")
        file:close()
        
        if content then
            -- Apply filters (timestamp with custom regex if provided)
            local filtered_content = filter_log_content(content, start_timestamp, end_timestamp, timestamp_regex, log_regex)
            
            ngx.say(filtered_content)
            return ngx.exit(ngx.HTTP_OK)  -- Explicitly end request processing
        else
            ngx.status = ngx.HTTP_NO_CONTENT
            return ngx.exit(ngx.HTTP_OK)  -- Explicitly end request processing
        end
    end
end
