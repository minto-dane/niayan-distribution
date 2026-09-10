-- SPDX-License-Identifier: MIT
-- Isolated qualification adapter; no production runtime modifications.
with Ada.Command_Line; with Ada.Text_IO;
with MC_Clock; with MC_FS; with MC_Hex; with MC_Runtime; with MC_Store;
with MC_Types; use MC_Types;
with Pkg_Archive_Supply;
procedure Chaos_Driver with SPARK_Mode => Off is
   Store : MC_Store.Store; Media : MC_FS.Root; File : MC_FS.File;
   Status : Outcome; Trusted : Pkg_Archive_Supply.Authority;
   Original, Control, Receipt, Binding, Hash : Digest := Zero_Digest;
   Now, Boot, Deadline, Size : Counter; Used : Natural;
   Stop : exception;
   procedure Need (Name : String) is
   begin
      if Status /= OK then
         Ada.Text_IO.Put_Line ("FAIL " & Name & " " & Outcome'Image (Status));
         raise Stop;
      end if;
   end Need;
   procedure Identity (Name : String; Value : out Digest) is
   begin
      MC_FS.Open_Read (Media, Name, File, Status); Need ("fixture-open");
      MC_FS.Hash (File, 16_777_216, Value, Size, Status); Need ("fixture-hash");
      MC_FS.Close (File);
   end Identity;
   procedure Import (Name : String) is
   begin
      MC_FS.Open_Read (Media, Name, File, Status); Need ("import-open");
      MC_Store.Import_File (Store, File, 16_777_216, Hash, Status);
      if Status /= OK and then Hash /= Zero_Digest then
         Ada.Text_IO.Put_Line ("VIOLATION failed import nonzero hash"); raise Stop;
      end if;
      Need ("import-" & Name); MC_FS.Close (File);
      Ada.Text_IO.Put_Line ("ACK " & Name & " " & MC_Hex.Encode (Hash)); Ada.Text_IO.Flush;
   end Import;
   procedure Read_Key (Name : String; Value : out Digest) is
   begin
      MC_FS.Open_Read (Media, Name, File, Status); Need ("key-open");
      MC_FS.Read_At (File, 0, Value, Used, Status); Need ("key-read"); MC_FS.Close (File);
      if Used /= 32 then raise Stop; end if;
   end Read_Key;
begin
   if Ada.Command_Line.Argument_Count /= 4 then raise Stop; end if;
   MC_Runtime.Initialize (Status); Need ("runtime");
   if Ada.Command_Line.Argument (1) = "init" then
      MC_Store.Initialize (Ada.Command_Line.Argument (2), Store, Status); Need ("initialize");
   else
      MC_Store.Open (Ada.Command_Line.Argument (2), Store, Status); Need ("reopen");
   end if;
   MC_FS.Open_Root (Ada.Command_Line.Argument (3), Media, Status); Need ("media");
   if Ada.Command_Line.Argument (1) = "import" then
      Import ("original.deb"); Import ("control"); Import ("policy"); Import ("InRelease");
      Import ("Packages"); Import ("keyring"); Import ("receipt");
   elsif Ada.Command_Line.Argument (1) in "verify" | "verify-wait" then
      Identity ("original.deb", Original); Identity ("control", Control); Identity ("receipt", Receipt);
      Read_Key ("public-key", Trusted.Key); Read_Key ("scope", Trusted.Scope);
      Trusted.Minimum_Epoch := 7; Trusted.Maximum_Age := 1_800;
      MC_Clock.Realtime_Seconds (Now, Status); Need ("UTC");
      MC_Clock.Boottime_Milliseconds (Boot, Status); Need ("boottime");
      Deadline := Boot + Counter'Value (Ada.Command_Line.Argument (4));
      if Ada.Command_Line.Argument (1) = "verify-wait" then
         Ada.Text_IO.Put_Line ("READY"); Ada.Text_IO.Flush;
         declare Line : constant String := Ada.Text_IO.Get_Line; begin
            if Line /= "continue" then raise Stop; end if;
         end;
      end if;
      Pkg_Archive_Supply.Verify_Original (Store, Receipt, Original, Control,
         Trusted, Now, Deadline, Binding, Status);
      Ada.Text_IO.Put_Line ("RESULT " & Outcome'Image (Status) & " " & MC_Hex.Encode (Binding));
      if (Status /= OK and then Binding /= Zero_Digest) or else
         (Status = OK and then Binding /= Receipt) then
         Ada.Text_IO.Put_Line ("VIOLATION incorrect binding"); raise Stop;
      end if;
      if Status /= OK then Ada.Command_Line.Set_Exit_Status (10); end if;
   elsif Ada.Command_Line.Argument (1) /= "init" then raise Stop;
   end if;
   MC_FS.Close (Media); MC_Store.Close (Store); Ada.Text_IO.Put_Line ("DONE");
exception
   when Stop => MC_FS.Close (File); MC_FS.Close (Media); MC_Store.Close (Store);
      Ada.Command_Line.Set_Exit_Status (11);
end Chaos_Driver;
