-- Studio Command Bar:
-- require(game.ServerStorage.Prompt2Particles.CIXExpansionRoundtrip)()

local function same(a, b)
	if type(a) ~= type(b) then return false end
	if type(a) ~= "table" then return a == b end
	for key, value in pairs(a) do
		if not same(value, b[key]) then return false end
	end
	for key in pairs(b) do
		if a[key] == nil then return false end
	end
	return true
end

local function run()
	local root = game.Workspace.Particles.Dataset
	local library = game.ServerStorage.Prompt2Particles
	local exporterCopy = library.Exporter:Clone()
	exporterCopy.Name = "ExporterForCIXExpansionTest"
	exporterCopy.Parent = library
	local exporter = require(exporterCopy)
	local importer = require(library.Importer)
	local effects = require(library.CIXExpansion).list()
	local mismatches = {}
	local warnings = 0
	local checks = 0

	for _, spec in ipairs(effects) do
		local attachment = root[spec.family][spec.id .. "_V01_Base"]
		local emitter = attachment.ParticleEmitter
		local record, rowWarnings = exporter.serialize(emitter, root)
		warnings += #rowWarnings
		local rebuilt, errors = importer.deserialize(record)
		if not rebuilt or (errors and #errors > 0) then
			table.insert(mismatches, spec.id .. ": import failed")
		else
			local copy = rebuilt:FindFirstChildWhichIsA("ParticleEmitter")
			for _, property in ipairs(exporter.PROPERTIES.ParticleEmitter) do
				checks += 1
				if not same(exporter.encodeValue(emitter[property]), exporter.encodeValue(copy[property])) then
					table.insert(mismatches, spec.id .. ": " .. property)
				end
			end
			if emitter:GetAttribute("EmitCount") ~= copy:GetAttribute("EmitCount") then
				table.insert(mismatches, spec.id .. ": EmitCount")
			end
			local prompt = rebuilt:FindFirstChild("Prompt")
			if not prompt or prompt.TextLabel.Text ~= spec.prompt then
				table.insert(mismatches, spec.id .. ": prompt")
			end
			if rebuilt:GetAttribute("Category") ~= spec.category or rebuilt:GetAttribute("Split") ~= spec.split then
				table.insert(mismatches, spec.id .. ": labels")
			end
			rebuilt:Destroy()
		end
	end
	exporterCopy:Destroy()
	print(string.format(
		"CIX expansion roundtrip: %d effects, %d property checks, %d warnings, %d mismatches",
		#effects, checks, warnings, #mismatches
	))
	for i = 1, math.min(20, #mismatches) do
		warn(mismatches[i])
	end
	assert(#mismatches == 0, "CIX expansion roundtrip failed")
	return true
end

return run
