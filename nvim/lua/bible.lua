-- bible.nvim — thin wrapper over the local `bible` CLI
-- (https://github.com/…/bible-cli — data at ~/.local/share/bible/bible.db)
--
--   :Bible john 3:16          floating passage
--   :BibleSearch still small  results into quickfix
--   :BibleRandom              a random verse in a float
--
-- Install: drop this in your lua path and call require("bible").setup(),
-- or add this file's directory and `lua require("bible").setup()`.

local M = {}

local function run(args, on_done)
	local cmd = vim.list_extend({ "bible", "--json" }, args)
	vim.system(cmd, { text = true }, function(out)
		if out.code ~= 0 or not out.stdout or out.stdout == "" then
			vim.schedule(function()
				vim.notify("bible: " .. (out.stderr or "no result"), vim.log.levels.WARN)
			end)
			return
		end
		local ok, data = pcall(vim.json.decode, out.stdout)
		vim.schedule(function()
			if ok then
				on_done(data)
			else
				vim.notify("bible: bad JSON", vim.log.levels.ERROR)
			end
		end)
	end)
end

local function float(lines, title)
	local width = math.min(88, math.max(40, vim.o.columns - 16))
	local height = math.min(#lines + 2, vim.o.lines - 8)
	local buf = vim.api.nvim_create_buf(false, true)
	vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
	vim.bo[buf].filetype = "markdown"
	vim.bo[buf].modifiable = false
	local win = vim.api.nvim_open_win(buf, true, {
		relative = "editor",
		width = width,
		height = height,
		row = math.floor((vim.o.lines - height) / 2),
		col = math.floor((vim.o.columns - width) / 2),
		style = "minimal",
		border = "rounded",
		title = " " .. title .. " ",
		title_pos = "center",
	})
	vim.wo[win].wrap = true
	vim.wo[win].linebreak = true
	vim.keymap.set("n", "q", function() vim.api.nvim_win_close(win, true) end, { buffer = buf })
end

local function passage(data)
	local lines = {}
	for _, v in ipairs(data.verses or {}) do
		table.insert(lines, ("%d  %s"):format(v.verse, v.text))
	end
	return lines
end

function M.setup()
	vim.api.nvim_create_user_command("Bible", function(opts)
		run(vim.split(opts.args, "%s+", { trimempty = true }), function(data)
			if data.verses then
				float(passage(data), data.reference or "Bible")
			end
		end)
	end, { nargs = "+", desc = "Read a passage in a float" })

	vim.api.nvim_create_user_command("BibleSearch", function(opts)
		run(vim.list_extend({ "search" }, vim.split(opts.args, "%s+", { trimempty = true })), function(data)
			local items = {}
			for _, r in ipairs(data.results or {}) do
				table.insert(items, { filename = r.reference, lnum = 1, text = r.text })
			end
			if #items == 0 then
				vim.notify("bible: no matches", vim.log.levels.INFO)
				return
			end
			vim.fn.setqflist({}, " ", {
				title = "bible: " .. opts.args,
				items = items,
			})
			vim.cmd("copen")
		end)
	end, { nargs = "+", desc = "Search scripture into quickfix" })

	vim.api.nvim_create_user_command("BibleRandom", function()
		run({ "random" }, function(data)
			if data.text then
				float({ data.text }, data.reference or "Bible")
			end
		end)
	end, { desc = "A random verse" })
end

return M
