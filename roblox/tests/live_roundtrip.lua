-- Runs against the emitters in the open place without adding instances to it.
local HttpService = game:GetService("HttpService")

local function describe(Exporter, value)
	local encoded, err = Exporter.encodeValue(value)
	return err and tostring(value) or HttpService:JSONEncode(encoded)
end

return function(Exporter, Importer, root, options)
	assert(Exporter and Importer, "pass the exporter and importer modules")
	assert(root, "pass the dataset root, e.g. workspace.Particles.Dataset")
	options = options or {}

	local list = Exporter.collect(root)
	local offset = options.offset or 0
	local limit = options.limit or #list
	assert(offset >= 0 and offset % 1 == 0, "offset must be a nonnegative integer")
	assert(limit >= 0 and limit % 1 == 0, "limit must be a nonnegative integer")
	local batch = Exporter.exportBatch(root, offset, limit)
	assert(batch.total == #list, "exportBatch total differs from collect")
	local batchLines = {}
	for _, row in ipairs(batch.lines) do
		assert(batchLines[row.id] == nil, "duplicate id in exportBatch: " .. row.id)
		batchLines[row.id] = row.line
	end

	local result = {
		total = #list,
		exported = #batch.lines,
		skipped = #batch.skipped,
		checked = 0,
		passed = 0,
		failed = 0,
		bursts = 0,
		continuous = 0,
		withEmitCount = 0,
		failures = {},
	}

	for i = offset + 1, math.min(#list, offset + limit) do
		local entry = list[i]
		local original = entry.emitter
		local scratch, rebuilt
		result.checked += 1

		local ok, err = pcall(function()
			local record, exportWarnings = Exporter.serialize(original, root)
			assert(#exportWarnings == 0, "export warnings: " .. table.concat(exportWarnings, " | "))
			for _, name in ipairs(Exporter.PROPERTIES.ParticleEmitter) do
				assert(record.emitter.properties[name] ~= nil, "export omitted " .. name)
			end
			local line = Exporter.encodeLine(record)
			local split = Exporter.splitOf(original)
			if split and not Exporter.EXCLUDED_SPLITS[split] then
				assert(batchLines[record.id] == line, "exportBatch line differs")
			else
				assert(batchLines[record.id] == nil, "exportBatch included an excluded record")
			end
			local parsed, parseError = Importer.parseLine(line)
			assert(parsed, parseError)
			local valid, validationErrors = Importer.validate(parsed)
			assert(valid, "invalid export: " .. table.concat(validationErrors, " | "))

			local count = original:GetAttribute("EmitCount")
			assert(count ~= nil, "EmitCount attribute is missing")
			local exportedCount = parsed.emitter.attributes and parsed.emitter.attributes.EmitCount
			assert(exportedCount == count, "EmitCount changed during export")
			assert(Importer.emitCount(parsed) == (count or 0), "playback count changed")
			assert(Importer.playbackMode(parsed) == parsed.playback_mode, "playback mode changed")

			local report
			rebuilt, report = Importer.deserialize(parsed)
			assert(rebuilt, "import failed: " .. table.concat(report.errors, " | "))
			assert(#report.errors == 0, "import errors: " .. table.concat(report.errors, " | "))

			local clonedEmitter = rebuilt:FindFirstChild(original.Name)
			assert(clonedEmitter and clonedEmitter:IsA("ParticleEmitter"), "rebuilt emitter is missing")
			assert(clonedEmitter:GetAttribute("EmitCount") == count, "EmitCount changed during import")
			for name in pairs(record.emitter.properties or {}) do
				local before, after = original[name], clonedEmitter[name]
				if not Importer.valuesEqual(before, after) then
					error(name .. ": expected " .. describe(Exporter, before) .. ", got " .. describe(Exporter, after))
				end
			end
			local sourceAttributes = original:GetAttributes()
			local rebuiltAttributes = clonedEmitter:GetAttributes()
			for name, before in pairs(sourceAttributes) do
				local after = rebuiltAttributes[name]
				if not Importer.valuesEqual(before, after) then
					error("attribute " .. name .. ": expected " .. describe(Exporter, before) .. ", got " .. describe(Exporter, after))
				end
			end
			for name in pairs(rebuiltAttributes) do
				assert(sourceAttributes[name] ~= nil, "unexpected attribute: " .. name)
			end
			local sourceDiff = Importer.apply(parsed, original.Parent)
			assert(#sourceDiff.errors == 0 and #sourceDiff.changes == 0, "export differs from source")
			local cloneDiff = Importer.apply(parsed, rebuilt)
			assert(#cloneDiff.errors == 0 and #cloneDiff.changes == 0, "import differs from export")

			-- The path must match for the second export to produce the same ID.
			scratch = Instance.new("Folder")
			local parent = scratch
			for j = 1, #parsed.path - 2 do
				local folder = Instance.new("Folder")
				folder.Name = parsed.path[j]
				folder.Parent = parent
				parent = folder
			end
			rebuilt.Parent = parent
			local again, reexportWarnings = Exporter.serialize(clonedEmitter, scratch)
			assert(#reexportWarnings == 0, "re-export warnings: " .. table.concat(reexportWarnings, " | "))
			assert(Exporter.encodeLine(again) == line, "canonical JSONL or row_hash changed")

			if count ~= nil then
				result.withEmitCount += 1
			end
			if count and count > 0 then
				result.bursts += 1
			else
				result.continuous += 1
			end
		end)

		if scratch then
			scratch:Destroy()
		elseif rebuilt then
			rebuilt:Destroy()
		end
		if ok then
			result.passed += 1
		else
			result.failed += 1
			if #result.failures < 20 then
				table.insert(result.failures, entry.id .. ": " .. tostring(err))
			end
		end
	end
	return result
end
